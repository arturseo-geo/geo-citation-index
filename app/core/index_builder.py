"""
Index Builder — materialises CitationIndex rows from BrandScore +
ArchetypeSnapshot data after each completed run.

The CitationIndex table is the public-facing source of truth.
The WordPress leaderboard reads from the JSON export produced here.
"""

import json
import logging
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import MAX_CITATION_INDEX_SNAPSHOTS, ARCHETYPE_PUBLIC_LABELS, OUTPUTS_DIR
from app.models.db import (
    Brand, BrandScore, ArchetypeSnapshot, CitationIndex,
    QueryRun, Platform, QueryVertical,
)

log = logging.getLogger(__name__)


def _trend_direction(delta_rank: int | None, is_new: bool) -> str:
    if is_new:
        return "new"
    if delta_rank is None:
        return "stable"
    if delta_rank > 2:
        return "rising"
    if delta_rank < -2:
        return "declining"
    return "stable"


def build_citation_index(run: QueryRun, db: Session) -> None:
    """
    Materialise CitationIndex rows for the completed run.

    For each (platform_slug, vertical_slug) combination:
      1. Rank brands by citation_score_normalised descending
      2. Attach archetype from ArchetypeSnapshot (cross-platform rows only)
      3. Write CitationIndex rows
      4. Prune old snapshots (retain last MAX_CITATION_INDEX_SNAPSHOTS runs)
      5. Set run.index_built = True
    """
    platforms = db.query(Platform).filter_by(is_active=True).all()
    verticals = db.query(QueryVertical).filter_by(is_active=True).all()

    run_date = run.run_date.date() if run.run_date else date.today()

    for platform in platforms:
        for vertical in verticals:
            _build_index_slice(
                run=run,
                platform=platform,
                vertical=vertical,
                run_date=run_date,
                db=db,
            )

        # Also build cross-vertical "all" slice per platform
        _build_index_slice(
            run=run,
            platform=platform,
            vertical=None,
            run_date=run_date,
            db=db,
        )

    _prune_old_index_snapshots(db)

    run.index_built = True
    db.commit()
    log.info(f"Citation index built for run {run.id}.")


def _build_index_slice(
    run: QueryRun,
    platform: Platform,
    vertical: QueryVertical | None,
    run_date: date,
    db: Session,
) -> None:
    vertical_id = vertical.id if vertical else None
    vertical_slug = vertical.slug if vertical else None

    scores = (
        db.query(BrandScore)
        .filter_by(
            run_id=run.id,
            platform_id=platform.id,
            vertical_id=vertical_id,
        )
        .order_by(BrandScore.citation_score_normalised.desc())
        .all()
    )
    if not scores:
        return

    for rank, bs in enumerate(scores, start=1):
        brand = db.query(Brand).get(bs.brand_id)
        if not brand or not brand.is_verified:
            continue  # Exclude unverified (llm-extracted) brands from public index

        archetype = None
        archetype_conf = None
        archetype_signals = None
        archetype_label = None

        if run.gap_analysis_valid and vertical_id is not None:
            snap = (
                db.query(ArchetypeSnapshot)
                .filter_by(run_id=run.id, brand_id=bs.brand_id, vertical_id=vertical_id)
                .first()
            )
            if snap:
                archetype = snap.citation_archetype
                archetype_conf = snap.archetype_confidence
                # Public signals only — no internal threshold values
                archetype_signals = {
                    "chatgpt_score": snap.chatgpt_score,
                    "perplexity_score": snap.perplexity_score,
                    "gemini_score": snap.gemini_score,
                    "perplexity_vs_chatgpt_delta": (
                        (snap.perplexity_score or 0) - (snap.chatgpt_score or 0)
                    ),
                }
                archetype_label = ARCHETYPE_PUBLIC_LABELS.get(archetype)

        ci = CitationIndex(
            index_type="brand",
            platform_slug=platform.slug,
            vertical_slug=vertical_slug,
            run_id=run.id,
            index_date=run_date,
            rank=rank,
            entity_id=brand.id,
            entity_name=brand.canonical_name,
            entity_slug=brand.slug,
            citation_score=bs.citation_score,
            citation_score_normalised=bs.citation_score_normalised,
            total_mentions=bs.total_mentions,
            queries_cited_in=bs.queries_cited_in,
            url_cited_count=bs.url_cited_count,
            first_position_count=bs.first_position_count,
            delta_rank=bs.delta_rank,
            is_new_entry=bs.is_new_entry,
            trend_direction=_trend_direction(bs.delta_rank, bs.is_new_entry),
            citation_archetype=archetype,
            archetype_confidence=archetype_conf,
            archetype_signals=archetype_signals,
            archetype_label_public=archetype_label,
            chatgpt_score=bs.chatgpt_score_this_run,
            perplexity_score=bs.perplexity_score_this_run,
            gemini_score=bs.gemini_score_this_run,
            platform_variance=bs.platform_variance,
            perplexity_vs_chatgpt_delta=bs.perplexity_vs_chatgpt_delta,
        )
        db.add(ci)


def _prune_old_index_snapshots(db: Session) -> None:
    """Keep only the last MAX_CITATION_INDEX_SNAPSHOTS runs in citation_index."""
    distinct_runs = (
        db.query(CitationIndex.run_id)
        .distinct()
        .order_by(CitationIndex.index_date.desc())
        .all()
    )
    run_ids = [r[0] for r in distinct_runs]
    if len(run_ids) > MAX_CITATION_INDEX_SNAPSHOTS:
        old_run_ids = run_ids[MAX_CITATION_INDEX_SNAPSHOTS:]
        db.query(CitationIndex).filter(CitationIndex.run_id.in_(old_run_ids)).delete(
            synchronize_session=False
        )
        db.commit()


def export_index_json(run: QueryRun, db: Session, output_dir: str = OUTPUTS_DIR) -> Path:
    """
    Export CitationIndex data for the run as JSON for the WordPress leaderboard.

    Output: outputs/YYYY-MM/index_data_YYYY-MM.json
    The leaderboard page reads this file. Upload to WordPress media library,
    update the JS variable in the page template to point to the new URL.
    """
    run_month = run.run_date.strftime("%Y-%m") if run.run_date else "unknown"
    out_dir = Path(output_dir) / run_month
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"index_data_{run_month}.json"

    rows = (
        db.query(CitationIndex)
        .filter_by(run_id=run.id)
        .order_by(
            CitationIndex.vertical_slug,
            CitationIndex.platform_slug,
            CitationIndex.rank,
        )
        .all()
    )

    data = {
        "meta": {
            "run_id": run.id,
            "run_date": run.run_date.isoformat() if run.run_date else None,
            "index_month": run_month,
            "gap_analysis_valid": run.gap_analysis_valid,
            "platforms": run.platforms_run,
        },
        "brands": [],
    }

    for row in rows:
        data["brands"].append({
            "entity_name": row.entity_name,
            "entity_slug": row.entity_slug,
            "platform": row.platform_slug,
            "vertical": row.vertical_slug,
            "rank": row.rank,
            "score": row.citation_score_normalised,
            "trend": row.trend_direction,
            "delta_rank": row.delta_rank,
            "archetype": row.citation_archetype,
            "archetype_label": row.archetype_label_public,
            "chatgpt_score": row.chatgpt_score,
            "perplexity_score": row.perplexity_score,
            "gemini_score": row.gemini_score,
            "perplexity_vs_chatgpt_delta": row.perplexity_vs_chatgpt_delta,
        })

    out_path.write_text(json.dumps(data, indent=2, default=str))
    log.info(f"Index JSON exported: {out_path}")
    return out_path
