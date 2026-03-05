"""
Shared fixtures for GEO Citation Index tests.
"""

import pytest
from unittest.mock import MagicMock
from datetime import datetime


@pytest.fixture
def mock_run():
    run = MagicMock()
    run.id = "run-test-001"
    run.run_date = datetime(2026, 3, 4)
    run.is_baseline = False
    run.gap_analysis_valid = True
    run.platforms_run = ["chatgpt", "perplexity", "gemini"]
    run.panel_id = "panel-001"
    run.status = "complete"
    return run


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.add = MagicMock()
    db.flush = MagicMock()
    db.commit = MagicMock()
    return db


@pytest.fixture
def mock_brand():
    b = MagicMock()
    b.id = "brand-001"
    b.canonical_name = "HubSpot"
    b.slug = "hubspot"
    b.is_verified = True
    b.latest_archetype = None
    return b
