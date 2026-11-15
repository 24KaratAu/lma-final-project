"""The demo walk-through: live tools on a dev clause, logged decisions read from a runs folder."""

import json
import re

from src.eval.demo import main

DEV = "data/dev/items.jsonl"


def plain(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _write_run(folder, name, item_id, verdict, f1=0.8):
    run = folder / name
    run.mkdir(parents=True)
    (run / "config.json").write_text(json.dumps({"git_commit": "abcdef1234"}))
    (run / "preds.jsonl").write_text(json.dumps({"item_id": item_id, "verdict": verdict, "cited_node": "ICA-28"}) + "\n")
    trace = {"item_id": item_id, "budget_spent": False,
             "transcript": [{"tool": "lookup_definition", "args": {"term": "Claim Period"}, "observation": {}}],
             "verify": {"verdict": verdict, "provision": "ICA-28", "confidence": 0.9,
                        "elements": {"effect_on_expiry": "claim_barred"}, "defect_type": "time_limit"}}
    (run / "traces.jsonl").write_text(json.dumps(trace) + "\n")
    overall = {"n": 1, "verdict_accuracy": 1.0, "defect_f1": f1}
    (run / "metrics.json").write_text(json.dumps({"overall": overall}))


def test_clause_runs_the_tools_live_without_logged_runs(tmp_path, capsys):
    assert main(["clause", "PL-20", "--items", DEV, "--runs", str(tmp_path)]) == 0
    out = plain(capsys.readouterr().out)
    assert "Clause PL-20" in out
    assert "Claim Period" in out  # the definition, found live in the lease graph
    assert "ICA-28" in out  # the statute search, live
    assert "No logged run found" in out
    assert "Lawyer:   VOID" in out


def test_clause_reads_the_logged_decision_and_marks_it(tmp_path, capsys):
    _write_run(tmp_path, "agent-controller-test", "PL-20", "void")
    _write_run(tmp_path, "B1-none-test", "PL-20", "valid")
    assert main(["clause", "PL-20", "--items", DEV, "--runs", str(tmp_path)]) == 0
    out = plain(capsys.readouterr().out)
    assert 'looked up "Claim Period"' in out
    assert "commit abcdef1" in out
    assert "effect on expiry:" in out
    assert "✓ correct" in out
    assert "Small model alone (B1): VALID ✗" in out


def test_clause_unknown_item(tmp_path, capsys):
    assert main(["clause", "XX-999", "--items", DEV, "--runs", str(tmp_path)]) == 1


def test_results_table_and_h3(tmp_path, capsys):
    _write_run(tmp_path, "agent-controller-test", "PL-20", "void", f1=0.8065)
    _write_run(tmp_path, "B2-none-test", "PL-20", "void", f1=0.9)
    assert main(["results", "--items", DEV, "--runs", str(tmp_path)]) == 0
    out = plain(capsys.readouterr().out)
    assert "0.807" in out  # rounded half up, as in the report
    assert "Frontier model alone (B2)" in out
    assert "H3, fixed before testing" in out


def test_results_without_runs(tmp_path):
    assert main(["results", "--items", DEV, "--runs", str(tmp_path)]) == 1
