"""Tests for the key-lawyer agreement (src/graph/agreement.py)."""

import pytest

from src.graph import agreement


def test_the_lawyers_answers_map_to_the_keys_labels():
    assert agreement.verdict("refer") == "handoff" and agreement.verdict("void") == "void"
    assert agreement.provision("s.28(b)") == "ICA-28"
    assert agreement.provision("s.27, Exception 1") == "ICA-27-E1"
    assert agreement.provision("s.28, Exception 3") == "ICA-28-E3"
    assert agreement.provision("outside scope (s.74)") is None
    assert agreement.section("ICA-28-E1") == "ICA-28" and agreement.section(None) is None


def test_kappa_is_one_for_full_agreement_and_zero_at_chance():
    assert agreement.kappa([("void", "void"), ("valid", "valid")]) == 1.0
    assert agreement.kappa([("a", "a"), ("a", "b"), ("b", "b"), ("b", "a")]) == 0.0


def test_every_test_item_has_a_key_a_final_label_and_a_blind_answer():
    rows = agreement.load()
    assert len(rows) == 340 and sum(r["pool"] for r in rows) == 70


def test_the_reported_figures_come_from_the_frozen_files():
    s = agreement.summary(agreement.load())
    assert (s["verdict"], s["section"], s["provision"]) == (326, 338, 334)
    assert s["kappa"] == pytest.approx(0.936, abs=5e-4)
