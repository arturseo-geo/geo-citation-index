"""
Tests for app/core/content_generator.py

Covers FAIL-009 from failure_registry.yml.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime


def make_mock_run(is_baseline=True, gap_valid=True):
    run = MagicMock()
    run.id = "run-test-001"
    run.run_date = datetime(2026, 3, 4)
    run.is_baseline = is_baseline
    run.gap_analysis_valid = gap_valid
    run.platforms_run = ["chatgpt", "perplexity", "gemini"]
    return run


# ── build_prompt_context ──────────────────────────────────────────────────────

def test_context_has_required_keys():
    """build_prompt_context must return all keys expected by generation prompts."""
    from app.core.content_generator import build_prompt_context

    run = make_mock_run()
    db = MagicMock()
    db.query.return_value.filter_by.return_value.order_by.return_value.limit.return_value.all.return_value = []
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    db.query.return_value.filter.return_value.distinct.return_value.all.return_value = []

    context = build_prompt_context(run, db)

    required_keys = [
        "run_month", "run_month_slug", "run_date", "gap_analysis_valid",
        "platforms_run", "top_brands", "biggest_gaps", "archetype_changes", "verticals",
    ]
    for key in required_keys:
        assert key in context, f"Missing key in context: {key}"


def test_context_run_month_format():
    """run_month must be human-readable (e.g. 'March 2026')."""
    from app.core.content_generator import build_prompt_context

    run = make_mock_run()
    db = MagicMock()
    db.query.return_value.filter_by.return_value.order_by.return_value.limit.return_value.all.return_value = []
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    db.query.return_value.filter.return_value.distinct.return_value.all.return_value = []

    context = build_prompt_context(run, db)
    assert context["run_month"] == "March 2026"
    assert context["run_month_slug"] == "2026-03"


# ── FAIL-009: First-run content ───────────────────────────────────────────────

def test_first_run_content_generation():
    """
    FAIL-009: Content generation must handle first-run context gracefully.
    delta_rank and archetype_changes will be empty/null on baseline runs.
    Context must not cause prompt to fail or produce obviously broken output.
    """
    from app.core.content_generator import build_prompt_context

    run = make_mock_run(is_baseline=True)
    db = MagicMock()

    # First run: no archetype changes, no deltas
    db.query.return_value.filter_by.return_value.order_by.return_value.limit.return_value.all.return_value = []
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    db.query.return_value.filter.return_value.distinct.return_value.all.return_value = []

    context = build_prompt_context(run, db)

    # Should not raise; archetype_changes should be empty list
    assert isinstance(context["archetype_changes"], list)
    assert len(context["archetype_changes"]) == 0
    assert isinstance(context["top_brands"], list)


# ── Output file naming ────────────────────────────────────────────────────────

def test_output_paths_use_run_month():
    """Output file names must include the run month slug."""
    from app.core.content_generator import generate_monthly_report
    from pathlib import Path

    run = make_mock_run()
    db = MagicMock()

    mock_context = {
        "run_month": "March 2026",
        "run_month_slug": "2026-03",
        "run_date": "2026-03-04",
        "gap_analysis_valid": True,
        "platforms_run": ["chatgpt", "perplexity", "gemini"],
        "top_brands": [],
        "biggest_gaps": [],
        "archetype_changes": [],
        "verticals": {},
    }

    with patch("app.core.content_generator.build_prompt_context", return_value=mock_context), \
         patch("app.core.content_generator.generate_blog_post", return_value="# Blog post"), \
         patch("app.core.content_generator.generate_social_posts", return_value="Post 1\n---\nPost 2"), \
         patch("app.core.content_generator.anthropic.Anthropic"), \
         patch("pathlib.Path.mkdir"), \
         patch("pathlib.Path.write_text"):

        run.report_generated = False
        db.commit = MagicMock()

        result = generate_monthly_report(run, db)

    assert "2026-03" in result["blog_post"]
    assert "2026-03" in result["social_posts"]
    assert result["run_month"] == "2026-03"
