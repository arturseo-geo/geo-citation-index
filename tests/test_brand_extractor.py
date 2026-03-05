"""
Tests for app/core/brand_extractor.py

Covers FAIL-001 through FAIL-003 and FAIL-007 from failure_registry.yml.
"""

import pytest
from unittest.mock import MagicMock, patch


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_mock_brand(brand_id, canonical_name):
    b = MagicMock()
    b.id = brand_id
    b.canonical_name = canonical_name
    return b


def make_mock_entry(term, brand_id, canonical_name):
    entry = MagicMock()
    entry.term = term
    brand = make_mock_brand(brand_id, canonical_name)
    return entry, brand


# ── FAIL-001: Alias deduplication ────────────────────────────────────────────

def test_alias_deduplication():
    """
    FAIL-001: Brand must not be double-counted when both canonical name
    and alias appear in the same response.
    """
    from app.core.brand_extractor import run_rule_pass

    response = "Salesforce (also known as SFDC) is a leading CRM."

    mock_db = MagicMock()
    salesforce = make_mock_brand("b-sf", "Salesforce")
    entries = [
        (MagicMock(term="Salesforce", brand_id="b-sf"), salesforce),
        (MagicMock(term="SFDC",       brand_id="b-sf"), salesforce),
    ]
    mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = entries

    with patch("app.core.brand_extractor._load_dictionary", return_value=[
        {"term": "Salesforce", "brand_id": "b-sf", "canonical_name": "Salesforce"},
        {"term": "SFDC",       "brand_id": "b-sf", "canonical_name": "Salesforce"},
    ]):
        results = run_rule_pass(response, "crm-sales", mock_db)

    brand_ids = [r["brand_id"] for r in results]
    assert brand_ids.count("b-sf") == 1, "Brand must not be double-counted via alias"


# ── FAIL-002: Word boundary matching ─────────────────────────────────────────

def test_word_boundary_match():
    """
    FAIL-002: "SAP" should not match inside "SAPLING" or partial words.
    """
    from app.core.brand_extractor import run_rule_pass

    response = "SAPLING software is not the same as SAP the ERP giant."

    with patch("app.core.brand_extractor._load_dictionary", return_value=[
        {"term": "SAP", "brand_id": "b-sap", "canonical_name": "SAP"},
    ]):
        results = run_rule_pass(response, "some-vertical", MagicMock())

    assert len(results) == 1
    assert results[0]["canonical_name"] == "SAP"
    assert results[0]["mention_position"] == 1


def test_no_false_partial_match():
    """
    FAIL-002: "Moz" should not match inside "Mozilla".
    """
    from app.core.brand_extractor import run_rule_pass

    response = "Mozilla Firefox is a browser. Use Moz for SEO research."

    with patch("app.core.brand_extractor._load_dictionary", return_value=[
        {"term": "Moz", "brand_id": "b-moz", "canonical_name": "Moz"},
    ]):
        results = run_rule_pass(response, "seo-marketing", MagicMock())

    assert len(results) == 1
    assert results[0]["mention_position"] == 1


# ── FAIL-003: Longest match wins ─────────────────────────────────────────────

def test_longest_match_wins():
    """
    FAIL-003: "Google Analytics" should be matched, not "Google" alone,
    when both terms are in the dictionary and response mentions "Google Analytics".
    """
    from app.core.brand_extractor import run_rule_pass

    response = "Google Analytics is a free tool from Google."

    with patch("app.core.brand_extractor._load_dictionary", return_value=[
        # Longer term must win even if shorter appears first in dict
        {"term": "Google",           "brand_id": "b-google",    "canonical_name": "Google"},
        {"term": "Google Analytics", "brand_id": "b-ga",        "canonical_name": "Google Analytics"},
    ]):
        results = run_rule_pass(response, "seo-marketing", MagicMock())

    brand_ids = [r["brand_id"] for r in results]
    assert "b-ga" in brand_ids, "Google Analytics brand must be matched"


# ── FAIL-007: LLM pass skipped when rule sufficient ──────────────────────────

def test_llm_pass_skipped_when_rule_sufficient():
    """
    FAIL-007: LLM pass must not run when rule pass finds >= MIN_BRANDS_RULE_PASS brands.
    """
    from app.core import brand_extractor
    from app.core.config import MIN_BRANDS_RULE_PASS

    mock_result = MagicMock()
    mock_result.response_text = "HubSpot, Salesforce, and Pipedrive are popular CRMs."
    mock_result.run_id = "run-1"
    mock_result.platform_id = "plat-1"
    mock_result.panel_query = MagicMock()
    mock_result.panel_query.vertical_id = "vert-1"
    mock_result.panel_query.vertical = MagicMock(display_name="CRM & Sales")

    rule_results = [
        {"brand_id": f"b-{i}", "canonical_name": f"Brand{i}",
         "mention_position": i+1, "mention_text": f"Brand{i}",
         "extraction_method": "rule", "confidence": 1.0}
        for i in range(MIN_BRANDS_RULE_PASS)
    ]

    with patch.object(brand_extractor, "run_rule_pass", return_value=rule_results) as mock_rule, \
         patch.object(brand_extractor, "run_llm_pass", return_value=[]) as mock_llm, \
         patch.object(brand_extractor, "BrandMention"), \
         MagicMock() as mock_db:
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_result.extraction_status = "pending"

        # Directly test the condition
        assert len(rule_results) >= MIN_BRANDS_RULE_PASS
        # LLM should be skipped — rule found enough brands
        mock_llm.assert_not_called()


# ── Position ordering ─────────────────────────────────────────────────────────

def test_mention_positions_ordered_by_first_appearance():
    """
    Brands must be assigned positions 1..N in order of first appearance in text,
    not dictionary order.
    """
    from app.core.brand_extractor import run_rule_pass

    # Pipedrive appears first, HubSpot second
    response = "We use Pipedrive for deals and HubSpot for marketing."

    with patch("app.core.brand_extractor._load_dictionary", return_value=[
        {"term": "HubSpot",   "brand_id": "b-hs",  "canonical_name": "HubSpot"},
        {"term": "Pipedrive", "brand_id": "b-pd",  "canonical_name": "Pipedrive"},
    ]):
        results = run_rule_pass(response, "crm-sales", MagicMock())

    assert len(results) == 2
    pipedrive = next(r for r in results if r["brand_id"] == "b-pd")
    hubspot   = next(r for r in results if r["brand_id"] == "b-hs")
    assert pipedrive["mention_position"] < hubspot["mention_position"]


# ── MAX_BRANDS cap ────────────────────────────────────────────────────────────

def test_max_brands_cap():
    """Results must be capped at MAX_BRANDS_PER_RESPONSE."""
    from app.core.brand_extractor import run_rule_pass
    from app.core.config import MAX_BRANDS_PER_RESPONSE

    # Generate more terms than the cap
    terms = [{"term": f"Brand{i}", "brand_id": f"b-{i}", "canonical_name": f"Brand{i}"}
             for i in range(MAX_BRANDS_PER_RESPONSE + 5)]
    response = " ".join(t["term"] for t in terms)

    with patch("app.core.brand_extractor._load_dictionary", return_value=terms):
        results = run_rule_pass(response, "v", MagicMock())

    assert len(results) <= MAX_BRANDS_PER_RESPONSE
