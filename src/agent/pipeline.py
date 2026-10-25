"""Fixed pipeline: one retrieve and one verify per clause.

This is the no-agent variant from the proposal and the placeholder for
run_agent until the controller agent lands in Phase 2.
"""

from src.common.schemas import ELEMENTS, Lease, Prediction


def run_agent(lease: Lease, config: dict) -> list[Prediction]:
    """Predict each target clause of one lease.

    config keys:
      targets   list of {"item_id", "clause_id"}; ids only, never gold labels
      retrieve  retrieve(clause_id, lease, mode, k) -> {"nodes", "path"}
      verify    verify(clause_text, evidence, elements) -> {"verdict", "provision", "confidence"}
      mode      retrieval mode: "none", "flat" or "graph" (default "graph")
      k         retrieval depth (default 5)
    """
    clauses = {c.clause_id: c for c in lease.clauses}
    preds = []
    for target in config["targets"]:
        clause = clauses[target["clause_id"]]
        evidence = config["retrieve"](clause.clause_id, lease, mode=config.get("mode", "graph"), k=config.get("k", 5))
        out = config["verify"](clause.text, evidence, ELEMENTS)
        preds.append(
            Prediction(
                item_id=target["item_id"],
                verdict=out["verdict"],
                cited_node=out["provision"],
                path=evidence["path"],
            )
        )
    return preds
