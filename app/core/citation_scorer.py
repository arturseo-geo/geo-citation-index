"""
Citation Scorer — aggregates BrandMention rows into BrandScore rows,
computes cross-platform deltas, classifies archetypes, and writes
ArchetypeSnapshot rows.

Reads from:  brand_mentions, query_runs, platforms, query_verticals
Writes to:   brand_scores, archetype_snapshots, brands.latest_archetype

Separation from brand_extractor.py is deliberate:
  - Extraction can be re-run if dictionary changes without invalidating scores.
  - Scoring can be recalibrated without touching extraction.
"""

import statistics
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import (
    POSITION_WEIGHTS,
    POSITION_WEIGHT_DEFAULT,
    URL_CITED_BONUS,
    ARCHETYPE_THRESHOLDS,
    ARCHETYPE_PRIORITY,
    ARCHETYPE_PUBLIC_LABELS,
    ARCHETYPE_THRESHOLD_VERSION,
)
from app.models.db import (
    Brand, BrandMention, BrandScore, ArchetypeSnapshot,
    QueryRun, Platform, QueryVertical,
)

log = logging.getLogger(__name__)


# ── Step 1: Raw citation scoring ──────────────────────────────────────────────

def compute_citation_score(mentions: list[BrandMention]) -> float:
    """
    Position-weighted citation score for a set of BrandMention rows.

    Weights:  pos 1 = 5, pos 2 = 3, pos 3 = 2, pos 4+ = 1
    Bonus:    +2 for each mention where url_cited = True

    Stores raw (un-normalised) score on BrandScore.citation_score.
    """
    score = 0.0
    for m in mentions:
        weight = POSITION_WEIGHTS.get(m.mention_position, POSITION_WEIGHT_DEFAULT)
        score += weight
        if m.url_cited:
            score += URL_CITED_BONUS
    return score


def normalise_scores(
    scores: dict[str, float],
    query_count: int,
) -> dict[str, float]:
    """
    Two-stage normalisation to 0-100 scale.

    Stage 1 — normalise by query count:
        per_query = raw_score / query_count

    Stage 2 — normalise within group:
        max_per_query = max(per_query.values())
        normalised = (per_query / max_per_query) * 100

    Rationale: raw scores are not comparable across verticals with
    different query counts or brand density. Normalised scores are.

    Returns empty dict if scores is empty or query_count is 0.
    """
    if not scores or query_count == 0:
        return {}

    per_query = {bid: raw / query_count for bid, raw in scores.items()}
    max_pq = max(per_query.values())
    if max_pq == 0:
        return {bid: 0.0 for bid in scores}
    return {bid: round((v / max_pq) * 100, 2) for bid, v in per_query.items()}


# ── Step 2: Cross-platform deltas ─────────────────────────────────────────────

def get_score_or_zero(
    brand_id: str,
    run_id: str,
    platform_slug: str,
    vertical_id: Optional[str],
    db: Session,
) -> float:
    """
    Fetch normalised citation score for a brand × platform × run.
    Returns 0.0 if no score exists — absence is valid data (not missing).
    A brand with chatgpt_normalised=60 and perplexity_normalised=0
    has a delta of -60. That IS the finding.
    """
    platform = db.query(Platform).filter_by(slug=platform_slug).first()
    if not platform:
        return 0.0
    score = db.query(BrandScore).filter_by(
        run_id=run_id,
        brand_id=brand_id,
        platform_id=platform.id,
        vertical_id=vertical_id,
    ).first()
    return score.citation_score_normalised if score else 0.0


def compute_cross_platform_deltas(run: QueryRun, db: Session) -> None:
    """
    Compute delta fields across all BrandScore rows for a completed run.

    For each brand × vertical:
      1. Fetch normalised scores for chatgpt, perplexity, gemini
      2. Compute deltas (perplexity−chatgpt, etc.)
      3. Compute platform_variance (stdev of all three)
      4. Denormalise onto each platform's BrandScore row

    Sets run.gap_analysis_valid = True if all 3 platforms have scores.
    Called after all platform scores are written.
    """
    # Get all unique (brand_id, vertical_id) pairs for this run
    scores = db.query(BrandScore).filter_by(run_id=run.id).all()
    pairs = {(s.brand_id, s.vertical_id) for s in scores}

    platforms_run = set(run.platforms_run or [])
    all_platforms_complete = {"chatgpt", "perplexity", "gemini"}.issubset(platforms_run)

    for brand_id, vertical_id in pairs:
        gpt   = get_score_or_zero(brand_id, run.id, "chatgpt",    vertical_id, db)
        perp  = get_score_or_zero(brand_id, run.id, "perplexity", vertical_id, db)
        gem   = get_score_or_zero(brand_id, run.id, "gemini",     vertical_id, db)

        perp_vs_gpt  = round(perp - gpt,  2)
        perp_vs_gem  = round(perp - gem,  2)
        gpt_vs_gem   = round(gpt  - gem,  2)
        variance     = round(statistics.stdev([gpt, perp, gem]), 2) if all_platforms_complete else None

        # Write delta fields to every platform's BrandScore row for this pair
        platform_scores = db.query(BrandScore).filter_by(
            run_id=run.id,
            brand_id=brand_id,
            vertical_id=vertical_id,
        ).all()

        for bs in platform_scores:
            bs.chatgpt_score_this_run      = gpt
            bs.perplexity_score_this_run   = perp
            bs.gemini_score_this_run       = gem
            bs.perplexity_vs_chatgpt_delta = perp_vs_gpt
            bs.perplexity_vs_gemini_delta  = perp_vs_gem
            bs.chatgpt_vs_gemini_delta     = gpt_vs_gem
            bs.platform_variance           = variance

    if all_platforms_complete:
        run.gap_analysis_valid = True

    db.commit()
    log.info(f"Cross-platform deltas written. gap_analysis_valid={run.gap_analysis_valid}")


# ── Step 3: Archetype classification ─────────────────────────────────────────

def classify_archetype(
    chatgpt_score: float,
    perplexity_score: float,
    gemini_score: float,
    perplexity_vs_chatgpt_delta: float,
    platform_variance: Optional[float],
    thresholds: dict = ARCHETYPE_THRESHOLDS,
    priority: list = ARCHETYPE_PRIORITY,
) -> tuple[str, float, dict]:
    """
    Classify a brand into one of five archetypes.

    Priority order (first match wins):
      1. consensus_dominant — all high, low variance
      2. ghost              — chatgpt ok, perplexity near zero
      3. training_dependent — chatgpt high, perplexity much lower
      4. retrieval_driven   — perplexity high, chatgpt lower
      5. consensus_geo      — moderate consistent, possible GEO effect
      6. unclassified       — no threshold met

    Returns:
        (archetype_slug, confidence_0_to_1, signals_dict)

    Confidence is how far scores exceed thresholds — not model certainty.
    Higher confidence = more strongly archetypal brand.
    """
    signals = {
        "chatgpt_score": chatgpt_score,
        "perplexity_score": perplexity_score,
        "gemini_score": gemini_score,
        "perplexity_vs_chatgpt_delta": perplexity_vs_chatgpt_delta,
        "platform_variance": platform_variance,
    }
    var = platform_variance if platform_variance is not None else 999

    t = thresholds

    # Check each archetype in ARCHETYPE_PRIORITY order (first match wins)
    for archetype in priority:
        th = t[archetype]

        if archetype == "consensus_dominant":
            if (chatgpt_score >= th["all_platforms_min"]
                    and perplexity_score >= th["all_platforms_min"]
                    and gemini_score >= th["all_platforms_min"]
                    and var <= th["platform_variance_max"]):
                conf = round(min(chatgpt_score, perplexity_score, gemini_score) / 100, 2)
                return "consensus_dominant", conf, signals

        elif archetype == "training_dependent":
            if (chatgpt_score >= th["chatgpt_min"]
                    and perplexity_vs_chatgpt_delta <= th["perplexity_vs_chatgpt_delta_max"]):
                conf = round(abs(perplexity_vs_chatgpt_delta) / 100, 2)
                return "training_dependent", conf, signals

        elif archetype == "ghost":
            delta_ok = "perplexity_vs_chatgpt_delta_max" not in th or perplexity_vs_chatgpt_delta <= th["perplexity_vs_chatgpt_delta_max"]
            if chatgpt_score >= th["chatgpt_min"] and perplexity_score <= th["perplexity_max"] and delta_ok:
                conf = round((chatgpt_score - perplexity_score) / 100, 2)
                return "ghost", conf, signals

        elif archetype == "retrieval_driven":
            if (perplexity_score >= th["perplexity_min"]
                    and perplexity_vs_chatgpt_delta >= th["perplexity_vs_chatgpt_delta_min"]):
                conf = round(perplexity_vs_chatgpt_delta / 100, 2)
                return "retrieval_driven", conf, signals

        elif archetype == "consensus_geo":
            if (chatgpt_score >= th["all_platforms_min"]
                    and chatgpt_score <= th["all_platforms_max"]
                    and perplexity_score >= th["all_platforms_min"]
                    and perplexity_score <= th["all_platforms_max"]
                    and gemini_score >= th["all_platforms_min"]
                    and gemini_score <= th["all_platforms_max"]
                    and var <= th["platform_variance_max"]):
                return "consensus_geo", 0.5, signals

    return "unclassified", 0.0, signals


def write_archetype_snapshots(run: QueryRun, db: Session) -> None:
    """
    For each (brand_id, vertical_id) pair with complete cross-platform
    delta data, classify archetype and write ArchetypeSnapshot row.

    run.gap_analysis_valid must be True before calling this.
    Skipped silently if gap_analysis_valid is False.
    """
    if not run.gap_analysis_valid:
        log.info("gap_analysis_valid=False — skipping archetype classification.")
        return

    # Get unique (brand_id, vertical_id) pairs from cross-platform delta rows
    scores = (
        db.query(BrandScore)
        .filter_by(run_id=run.id)
        .filter(BrandScore.perplexity_vs_chatgpt_delta.isnot(None))
        .all()
    )
    pairs = {(s.brand_id, s.vertical_id) for s in scores}

    for brand_id, vertical_id in pairs:
        # Get one score row that has all deltas (any platform's row is fine)
        ref_score = db.query(BrandScore).filter_by(
            run_id=run.id,
            brand_id=brand_id,
            vertical_id=vertical_id,
        ).first()
        if not ref_score:
            continue

        archetype, confidence, signals = classify_archetype(
            chatgpt_score=ref_score.chatgpt_score_this_run or 0.0,
            perplexity_score=ref_score.perplexity_score_this_run or 0.0,
            gemini_score=ref_score.gemini_score_this_run or 0.0,
            perplexity_vs_chatgpt_delta=ref_score.perplexity_vs_chatgpt_delta or 0.0,
            platform_variance=ref_score.platform_variance,
        )

        # Fetch previous snapshot for this brand × vertical
        prev = (
            db.query(ArchetypeSnapshot)
            .filter_by(brand_id=brand_id, vertical_id=vertical_id)
            .filter(ArchetypeSnapshot.run_id != run.id)
            .order_by(ArchetypeSnapshot.run_date.desc())
            .first()
        )
        prev_archetype = prev.citation_archetype if prev else None

        snapshot = ArchetypeSnapshot(
            run_id=run.id,
            brand_id=brand_id,
            vertical_id=vertical_id,
            run_date=run.run_date,
            citation_archetype=archetype,
            archetype_confidence=confidence,
            archetype_signals=signals,
            archetype_threshold_version=ARCHETYPE_THRESHOLD_VERSION,
            previous_archetype=prev_archetype,
            archetype_changed=(prev_archetype is not None and prev_archetype != archetype),
            chatgpt_score=ref_score.chatgpt_score_this_run,
            perplexity_score=ref_score.perplexity_score_this_run,
            gemini_score=ref_score.gemini_score_this_run,
            platform_variance=ref_score.platform_variance,
        )
        db.add(snapshot)

        # Update brand's latest_archetype
        brand = db.query(Brand).get(brand_id)
        if brand:
            brand.latest_archetype = archetype

    run.archetype_complete = True
    db.commit()
    log.info(f"Archetype snapshots written for run {run.id}.")


# ── Orchestrator ──────────────────────────────────────────────────────────────

def compute_brand_scores(run: QueryRun, db: Session) -> None:
    """
    Full scoring pipeline for a completed QueryRun.

    Steps:
      1. Aggregate BrandMention rows → raw citation_score per brand × platform × vertical
      2. Normalise scores within platform × vertical × run
      3. Write BrandScore rows
      4. Compute cross-platform deltas
      5. Classify archetypes and write ArchetypeSnapshot rows

    Sets run.scoring_complete = True on success.
    """
    from app.models.db import RunResult

    # Step 1 & 2: Group mentions by (brand, platform, vertical)
    results = db.query(RunResult).filter_by(run_id=run.id, status="complete").all()

    # Structure: {(platform_id, vertical_id): {brand_id: [mentions]}}
    grouped: dict = {}
    query_counts: dict = {}  # (platform_id, vertical_id) → number of queries

    for result in results:
        platform_id = result.platform_id
        vertical_id = result.panel_query.vertical_id if result.panel_query else None
        key = (platform_id, vertical_id)

        grouped.setdefault(key, {})
        query_counts[key] = query_counts.get(key, 0) + 1

        for mention in result.mentions:
            grouped[key].setdefault(mention.brand_id, []).append(mention)

    # Step 3: Compute raw scores and normalise
    for (platform_id, vertical_id), brand_mentions in grouped.items():
        raw_scores = {
            brand_id: compute_citation_score(mentions)
            for brand_id, mentions in brand_mentions.items()
        }
        q_count = query_counts.get((platform_id, vertical_id), 1)
        norm_scores = normalise_scores(raw_scores, q_count)

        # Rank brands by normalised score descending
        ranked = sorted(norm_scores.items(), key=lambda x: x[1], reverse=True)

        # Fetch baseline run for deltas
        baseline_run = (
            db.query(QueryRun)
            .filter_by(panel_id=run.panel_id, is_baseline=True)
            .first()
        )

        for rank, (brand_id, norm_score) in enumerate(ranked, start=1):
            mentions = brand_mentions[brand_id]

            # Baseline delta
            baseline_run_id = None
            delta_score = None
            delta_rank = None
            if baseline_run and baseline_run.id != run.id:
                baseline_run_id = baseline_run.id
                prev = db.query(BrandScore).filter_by(
                    run_id=baseline_run.id,
                    brand_id=brand_id,
                    platform_id=platform_id,
                    vertical_id=vertical_id,
                ).first()
                if prev:
                    delta_score = round(norm_score - prev.citation_score_normalised, 2)
                    delta_rank = (prev.rank - rank) if prev.rank else None

            bs = BrandScore(
                run_id=run.id,
                brand_id=brand_id,
                platform_id=platform_id,
                vertical_id=vertical_id,
                total_mentions=len(mentions),
                queries_cited_in=len({m.result_id for m in mentions}),
                first_position_count=sum(1 for m in mentions if m.mention_position == 1),
                url_cited_count=sum(1 for m in mentions if m.url_cited),
                citation_score=raw_scores[brand_id],
                citation_score_normalised=norm_score,
                rank=rank,
                baseline_run_id=baseline_run_id,
                delta_citation_score=delta_score,
                delta_rank=delta_rank,
                is_new_entry=(baseline_run_id is not None and delta_score is None),
            )
            db.add(bs)

    db.flush()

    # Step 4: Cross-platform deltas
    compute_cross_platform_deltas(run, db)

    # Step 5: Archetypes
    write_archetype_snapshots(run, db)

    run.scoring_complete = True
    db.commit()
    log.info(f"Scoring complete for run {run.id}.")
