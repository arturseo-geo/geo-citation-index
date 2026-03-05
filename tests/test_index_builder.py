"""
Tests for app/core/index_builder.py
"""

import pytest
from unittest.mock import MagicMock, patch


def test_trend_direction_rising():
    from app.core.index_builder import _trend_direction
    assert _trend_direction(delta_rank=5, is_new=False) == "rising"


def test_trend_direction_declining():
    from app.core.index_builder import _trend_direction
    assert _trend_direction(delta_rank=-5, is_new=False) == "declining"


def test_trend_direction_stable():
    from app.core.index_builder import _trend_direction
    assert _trend_direction(delta_rank=1, is_new=False) == "stable"
    assert _trend_direction(delta_rank=None, is_new=False) == "stable"


def test_trend_direction_new():
    from app.core.index_builder import _trend_direction
    assert _trend_direction(delta_rank=None, is_new=True) == "new"


def test_export_index_json_structure(tmp_path):
    """Exported JSON must have 'meta' and 'brands' keys."""
    from app.core.index_builder import export_index_json
    from datetime import datetime

    run = MagicMock()
    run.id = "run-001"
    run.run_date = datetime(2026, 3, 4)
    run.gap_analysis_valid = True
    run.platforms_run = ["chatgpt", "perplexity", "gemini"]

    db = MagicMock()
    db.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = []

    with patch("app.core.index_builder.OUTPUTS_DIR", str(tmp_path)):
        out_path = export_index_json(run, db)

    import json
    data = json.loads(out_path.read_text())
    assert "meta" in data
    assert "brands" in data
    assert data["meta"]["run_id"] == "run-001"
    assert data["meta"]["gap_analysis_valid"] is True
