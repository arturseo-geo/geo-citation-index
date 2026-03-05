"""
Brand Extractor — two-pass extraction pipeline.

Pass 1 (rule-based): string-match against brand_dictionary. Fast, cheap.
Pass 2 (LLM-assisted): only runs when Pass 1 finds < MIN_BRANDS_RULE_PASS.
                       Catches new/unknown brands. Updates dictionary.

New brands discovered by LLM pass are created with is_verified=False and
excluded from the public index until manually verified.
"""

import re
import json
import time
import logging
from datetime import datetime
from typing import Optional

import anthropic
from sqlalchemy.orm import Session

from app.core.config import (
    MIN_BRANDS_RULE_PASS,
    LLM_EXTRACTION_MODEL,
    LLM_EXTRACTION_CONFIDENCE,
    RULE_EXTRACTION_CONFIDENCE,
    MAX_BRANDS_PER_RESPONSE,
    ANTHROPIC_API_KEY,
)
from app.models.db import (
    Brand, BrandDictionaryEntry, BrandMention, RunResult,
    ExtractionRun, QueryRun,
)

log = logging.getLogger(__name__)


# ── Pass 1: Rule-Based ────────────────────────────────────────────────────────

def _load_dictionary(vertical_id: str, db: Session) -> list[dict]:
    """
    Load brand dictionary terms for a vertical (plus cross-vertical terms).
    Returns list of {"term": str, "brand_id": str, "canonical_name": str}
    sorted by term length descending so longest match wins.
    (Prevents "Google" matching before "Google Analytics" — FAIL-008 guard.)
    """
    entries = (
        db.query(BrandDictionaryEntry, Brand)
        .join(Brand, BrandDictionaryEntry.brand_id == Brand.id, isouter=True)
        .filter(BrandDictionaryEntry.vertical_id == vertical_id)
        .all()
    )
    result = []
    for entry, brand in entries:
        if brand:
            result.append({
                "term": entry.term,
                "brand_id": brand.id,
                "canonical_name": brand.canonical_name,
            })
    return sorted(result, key=lambda x: len(x["term"]), reverse=True)


def run_rule_pass(
    response_text: str,
    vertical_id: str,
    db: Session,
) -> list[dict]:
    """
    Match brand dictionary terms against response text.

    Returns list of match dicts ordered by first appearance:
    [{"brand_id", "canonical_name", "mention_position", "mention_text",
      "extraction_method", "confidence"}, ...]
    """
    match_terms = _load_dictionary(vertical_id, db)
    normalised = response_text.lower()
    matches = []
    matched_brand_ids: set[str] = set()

    for entry in match_terms:
        brand_id = entry["brand_id"]
        if brand_id in matched_brand_ids:
            continue  # FAIL-006 guard: no double-counting via aliases

        term = entry["term"]
        term_lower = term.lower()

        # Word-boundary check to prevent partial matches (e.g. "SAP" in "SAPSAP")
        pattern = r"\b" + re.escape(term_lower) + r"\b"
        match = re.search(pattern, normalised)
        if not match:
            continue

        # Extract original-casing text span
        start, end = match.start(), match.end()
        mention_text = response_text[start:end].strip(".,;:!?\"'")

        matches.append({
            "brand_id": brand_id,
            "canonical_name": entry["canonical_name"],
            "char_position": start,
            "mention_text": mention_text,
            "extraction_method": "rule",
            "confidence": RULE_EXTRACTION_CONFIDENCE,
        })
        matched_brand_ids.add(brand_id)

    # Sort by first appearance position, assign mention_position 1..N
    matches.sort(key=lambda x: x["char_position"])
    for i, m in enumerate(matches[:MAX_BRANDS_PER_RESPONSE]):
        m["mention_position"] = i + 1

    return matches[:MAX_BRANDS_PER_RESPONSE]


# ── Pass 2: LLM-Assisted ──────────────────────────────────────────────────────

_EXTRACTION_PROMPT = """\
You are extracting brand and product names from a text passage.

TEXT TO ANALYSE:
{response_text}

ALREADY IDENTIFIED (do not repeat these):
{already_found}

VERTICAL CONTEXT: {vertical_name}

INSTRUCTIONS:
1. List every company name, software product, or SaaS tool mentioned in the text,
   in the order they first appear.
2. Use the most specific product name when a company is referenced in context of
   a product. Example: "Google Analytics" not "Google" if that is what is discussed.
3. Do not include generic category terms (e.g. "CRM software", "email tool") — only
   named brands.
4. Do not include brands already in the ALREADY IDENTIFIED list.
5. Return ONLY a JSON array. No preamble, no explanation, no markdown fences.

RESPONSE FORMAT:
[
  {{"brand": "ExactBrandName", "position": 1}},
  {{"brand": "AnotherBrand", "position": 2}}
]

If no additional brands are found, return: []
"""


def run_llm_pass(
    response_text: str,
    vertical_id: str,
    vertical_name: str,
    rule_pass_results: list[dict],
    db: Session,
) -> list[dict]:
    """
    Use Claude to extract brands missed by the rule pass.
    Only called when len(rule_pass_results) < MIN_BRANDS_RULE_PASS.
    Returns NEW matches only (not already in rule_pass_results).
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    already_found = [r["canonical_name"] for r in rule_pass_results]

    prompt = _EXTRACTION_PROMPT.format(
        response_text=response_text[:3000],  # cap to avoid token overrun
        already_found=", ".join(already_found) if already_found else "(none)",
        vertical_name=vertical_name,
    )

    try:
        response = client.messages.create(
            model=LLM_EXTRACTION_MODEL,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
    except Exception as e:
        log.warning(f"LLM extraction API error: {e}")
        return []

    # Strip markdown fences if present
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        items = json.loads(raw)
        if not isinstance(items, list):
            return []
    except json.JSONDecodeError:
        log.warning(f"LLM extraction returned invalid JSON: {raw[:200]}")
        return []

    new_matches = []
    existing_brand_ids = {r["brand_id"] for r in rule_pass_results}
    next_position = len(rule_pass_results) + 1

    for item in items:
        if not isinstance(item, dict) or "brand" not in item:
            continue

        raw_name = str(item["brand"]).strip()
        # Normalise: strip leading/trailing punctuation
        normalised_name = re.sub(r"[^\w\s\-\.]", "", raw_name).strip()
        if not normalised_name:
            continue

        # Look up in brands table (case-insensitive)
        brand = db.query(Brand).filter(
            Brand.canonical_name.ilike(normalised_name)
        ).first()

        if brand and brand.id in existing_brand_ids:
            continue

        if not brand:
            # New brand discovery — create unverified record
            slug = re.sub(r"[^\w\-]", "-", normalised_name.lower()).strip("-")
            brand = Brand(
                canonical_name=normalised_name,
                slug=slug,
                source="llm_extracted",
                is_verified=False,
                vertical_id=vertical_id,
                aliases=[],
            )
            db.add(brand)
            db.flush()
            log.info(f"New brand discovered: {normalised_name} (unverified)")

        new_matches.append({
            "brand_id": brand.id,
            "canonical_name": brand.canonical_name,
            "mention_position": next_position,
            "mention_text": raw_name,
            "extraction_method": "llm",
            "confidence": LLM_EXTRACTION_CONFIDENCE,
        })
        existing_brand_ids.add(brand.id)
        next_position += 1

    return new_matches


# ── Main extraction functions ─────────────────────────────────────────────────

def extract_brands_from_result(
    result: RunResult,
    vertical_id: str,
    vertical_name: str,
    db: Session,
) -> list[BrandMention]:
    """
    Orchestrate Pass 1 and Pass 2 for a single RunResult.
    Writes BrandMention rows to DB. Updates result.extraction_status.
    """
    result.extraction_status = "rule_pass_running"
    db.flush()

    pass1 = run_rule_pass(result.response_text or "", vertical_id, db)
    result.extraction_status = "rule_pass_done"
    db.flush()

    all_matches = list(pass1)

    if len(pass1) < MIN_BRANDS_RULE_PASS:
        result.extraction_status = "llm_pass_running"
        db.flush()
        pass2 = run_llm_pass(
            result.response_text or "",
            vertical_id,
            vertical_name,
            pass1,
            db,
        )
        all_matches.extend(pass2)
        result.extraction_status = "llm_pass_done"
        db.flush()

    mentions = []
    for m in all_matches[:MAX_BRANDS_PER_RESPONSE]:
        mention = BrandMention(
            result_id=result.id,
            brand_id=m["brand_id"],
            run_id=result.run_id,
            platform_id=result.platform_id,
            mention_position=m["mention_position"],
            mention_text=m.get("mention_text"),
            extraction_method=m["extraction_method"],
            confidence=m["confidence"],
            url_cited=False,
        )
        db.add(mention)
        mentions.append(mention)

    result.extraction_status = "complete"
    db.commit()
    return mentions


def extract_brands_from_run(run: QueryRun, db: Session) -> ExtractionRun:
    """
    Run extraction across all RunResults for a QueryRun.
    Creates ExtractionRun audit record.
    Individual result failures are logged but do not abort the batch.
    """
    start_time = time.time()
    extraction_run = ExtractionRun(
        query_run_id=run.id,
        pass_type="rule+llm",
        results_processed=0,
        brands_found=0,
        new_brands_discovered=0,
        errors=0,
        error_log=[],
    )
    db.add(extraction_run)
    db.flush()

    # Load panel query vertical mapping
    results = db.query(RunResult).filter_by(run_id=run.id, status="complete").all()

    new_brands_before = db.query(Brand).filter_by(source="llm_extracted").count()

    for result in results:
        extraction_run.results_processed += 1
        try:
            # Get vertical from the panel query
            pq = result.panel_query
            vertical_id = pq.vertical_id if pq else None
            vertical_name = ""
            if pq and pq.vertical:
                vertical_name = pq.vertical.display_name

            if not vertical_id:
                continue

            mentions = extract_brands_from_result(
                result, vertical_id, vertical_name, db
            )
            extraction_run.brands_found += len(mentions)
        except Exception as e:
            extraction_run.errors += 1
            extraction_run.error_log.append({
                "result_id": result.id,
                "error": str(e),
            })
            log.error(f"Extraction error for result {result.id}: {e}")

    new_brands_after = db.query(Brand).filter_by(source="llm_extracted").count()
    extraction_run.new_brands_discovered = max(0, new_brands_after - new_brands_before)
    extraction_run.duration_seconds = round(time.time() - start_time, 2)
    extraction_run.status = "partial" if extraction_run.errors > 0 else "complete"

    run.extraction_complete = True
    db.commit()
    return extraction_run
