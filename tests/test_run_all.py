"""Run-all plan, chunks and results table, on the fixtures with the mock backend."""

from pathlib import Path

import pytest

from src.eval import run_all

FIX = Path(__file__).parent / "fixtures"


def test_plan_skips_adapter_configs_without_an_adapter():
    names = [c["name"] for c in run_all.plan(100, None)]
    assert "B1-none" in names and "agent-fixed-noadapter" in names
    assert "agent-fixed" not in names and "agent-controller" not in names
    assert all(not n.startswith("B2") for n in names)
    assert {c["name"] for c in run_all.plan(100, None, "laptop")} == {"B2-none", "B2-flat"}


def test_chunks_balance_hours():
    configs = run_all.plan(340, "adapter")
    bins = run_all.chunk(configs, 2)
    assert sorted(c["name"] for b in bins for c in b) == sorted(c["name"] for c in configs)
    hours = [sum(c["hours"] for c in b) for b in bins]
    assert max(hours) - min(hours) <= max(c["hours"] for c in configs)
    assert max(hours) < 12  # each chunk fits one Kaggle session


def test_laptop_needs_a_frontier_model():
    with pytest.raises(SystemExit):
        run_all.main(["--items", str(FIX / "items.jsonl"), "--where", "laptop"])


def test_runs_a_chunk_and_prints_the_table(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(run_all, "OPEN", "mock-model")
    real = run_all.argv_for
    monkeypatch.setattr(run_all, "argv_for", lambda cfg, a: [x if x != "hf" else "mock" for x in real(cfg, a)])
    run_all.main(["--items", str(FIX / "items.jsonl"), "--leases", str(FIX / "leases"), "--chunks", "2", "--chunk", "1",
                  "--out", str(tmp_path)])
    out = capsys.readouterr().out
    assert "chunk 1:" in out and "| Run | n |" in out
    ran = {p.parent.name for p in tmp_path.glob("*/metrics.json")}
    assert ran and all(r.endswith("-fixtures") for r in ran)
    assert run_all.table(str(tmp_path)).count("\n") == len(ran) + 1
