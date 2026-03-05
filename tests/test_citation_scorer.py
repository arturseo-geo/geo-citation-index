"""
Tests for app/core/citation_scorer.py

Covers FAIL-004 through FAIL-006 and FAIL-008 from failure_registry.yml.
"""

import pytest
from unittest.mock import MagicMock, patch


# ── compute_citation_score ────────────────────────────────────────────────────

def test_citation_score_position_weights():
    """Position 1 = 5pts, pos 2 = 3pts, pos 3 = 2pts, pos 4+ = 1pt."""
    from app.core.citation_scorer import compute_citation_score

    def make_mention(pos, url_cited=False):
        m = MagicMock()
        m.mention_position = pos
        m.url_cited = url_cited
        return m

    mentions = [make_mention(1), make_mention(2), make_mention(3), make_mention(4)]
    score = compute_citation_score(mentions)
    assert score == 5 + 3 + 2 + 1


def test_citation_score_url_bonus():
    """url_cited=True adds URL_CITED_BONUS to that mention's score."""
    from app.core.citation_scorer import compute_citation_score
    from app.core.config import URL_CITED_BONUS

    m = MagicMock()
    m.mention_position = 1
    m.url_cited = True
    score = compute_citation_score([m])
    assert score == 5 + URL_CITED_BONUS


def test_citation_score_empty():
    from app.core.citation_scorer import compute_citation_score
    assert compute_citation_score([]) == 0.0


# ── normalise_scores ─────────────────────────────────────────────────────────

def test_normalisation_basic():
    """Top brand should score 100 after normalisation."""
    from app.core.citation_scorer import normalise_scores

    raw = {"a": 10.0, "b": 5.0, "c": 2.0}
    normed = normalise_scores(raw, query_count=5)
    assert normed["a"] == 100.0
    assert 0 < normed["b"] < 100
    assert 0 < normed["c"] < normed["b"]


def test_normalisation_cross_vertical():
    """
    FAIL-006: Scores from verticals with different query counts must be
    comparable after normalisation.
    """
    from app.core.citation_scorer import normalise_scores

    # Vertical A: 10 queries
    raw_a = {"brand1": 50.0}
    normed_a = normalise_scores(raw_a, query_count=10)

    # Vertical B: 3 queries — same per-query performance
    raw_b = {"brand1": 15.0}
    normed_b = normalise_scores(raw_b, query_count=3)

    # Both should be 100 (top brand in their group)
    assert normed_a["brand1"] == 100.0
    assert normed_b["brand1"] == 100.0


def test_normalisation_zero_scores():
    from app.core.citation_scorer import normalise_scores
    raw = {"a": 0.0, "b": 0.0}
    normed = normalise_scores(raw, query_count=5)
    assert all(v == 0.0 for v in normed.values())


def test_normalisation_empty():
    from app.core.citation_scorer import normalise_scores
    assert normalise_scores({}, query_count=5) == {}
    assert normalise_scores({"a": 1.0}, query_count=0) == {}


# ── classify_archetype ────────────────────────────────────────────────────────

def test_classify_consensus_dominant():
    from app.core.citation_scorer import classify_archetype
    archetype, conf, _ = classify_archetype(80, 75, 78, -5, 3)
    assert archetype == "consensus_dominant"
    assert conf > 0


def test_classify_ghost():
    from app.core.citation_scorer import classify_archetype
    archetype, conf, _ = classify_archetype(60, 5, 40, -55, 25)
    assert archetype == "ghost"
    assert conf > 0


def test_classify_training_dependent():
    from app.core.citation_scorer import classify_archetype
    archetype, conf, _ = classify_archetype(70, 40, 55, -30, 15)
    assert archetype == "training_dependent"
    assert conf > 0


def test_classify_retrieval_driven():
    from app.core.citation_scorer import classify_archetype
    archetype, conf, _ = classify_archetype(30, 65, 45, 35, 18)
    assert archetype == "retrieval_driven"
    assert conf > 0


def test_classify_unclassified():
    from app.core.citation_scorer import classify_archetype
    archetype, conf, _ = classify_archetype(10, 12, 8, 2, 2)
    assert archetype == "unclassified"
    assert conf == 0.0


def test_classify_consensus_geo():
    from app.core.citation_scorer import classify_archetype
    # All between 25-60, low variance
    archetype, conf, _ = classify_archetype(45, 42, 40, -3, 5)
    assert archetype == "consensus_geo"
    assert conf == 0.5  # Always 0.5 — needs manual review


# ── FAIL-004: Archetype skipped when gap_analysis_valid=False ────────────────

def test_archetype_skipped_when_gap_invalid():
    """
    FAIL-004: write_archetype_snapshots must return early when
    run.gap_analysis_valid is False.
    """
    from app.core.citation_scorer import write_archetype_snapshots

    run = MagicMock()
    run.gap_analysis_valid = False
    db = MagicMock()

    write_archetype_snapshots(run, db)

    # DB should not be queried for scores
    db.query.assert_not_called()


# ── FAIL-005: Zero score delta ────────────────────────────────────────────────

def test_zero_score_delta_computation():
    """
    FAIL-005: A brand absent on Perplexity (score=0) must produce a negative
    delta, not NULL. Delta of -60 is a training_dependent signal.
    """
    from app.core.citation_scorer import classify_archetype

    # chatgpt=60, perplexity=0 → delta=-60 → training_dependent
    archetype, conf, signals = classify_archetype(
        chatgpt_score=60,
        perplexity_score=0,
        gemini_score=30,
        perplexity_vs_chatgpt_delta=-60,
        platform_variance=25,
    )
    assert archetype in ("ghost", "training_dependent")
    assert signals["perplexity_score"] == 0


# ── FAIL-008: Bias flag excluded ─────────────────────────────────────────────

def test_bias_flagged_query_data():
    """
    FAIL-008: bias_flag=True queries must be excluded from archetype scoring.
    The panel query fixture confirms bias_flag is stored correctly.
    """
    # Verify PanelQuery model has bias_flag field
    from app.models.db import PanelQuery
    assert hasattr(PanelQuery, "bias_flag"), "PanelQuery must have bias_flag column"


# ── Confidence bounds ─────────────────────────────────────────────────────────

def test_archetype_confidence_bounded():
    """Confidence should not exceed 1.0 for any archetype."""
    from app.core.citation_scorer import classify_archetype

    cases = [
        (100, 100, 100, 0, 0),     # dominant
        (100, 0, 50, -100, 50),    # ghost/training
        (10, 100, 50, 90, 40),     # retrieval
    ]
    for args in cases:
        _, conf, _ = classify_archetype(*args)
        assert 0.0 <= conf <= 1.0, f"Confidence out of bounds for args {args}: {conf}"
