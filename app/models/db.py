"""
Database models for the GEO Citation Index.

SQLite by default (single file, zero admin, adequate for monthly batch runs).
Migrate to PostgreSQL if concurrent writes or multi-user scale require it.

13 tables:
  platforms, query_verticals, brands, brand_dictionary,
  query_panels, panel_queries, query_runs, run_results,
  brand_mentions, brand_scores, archetype_snapshots,
  citation_index, extraction_runs
"""

import json
from datetime import datetime, date
from uuid import uuid4

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, Date, DateTime,
    ForeignKey, UniqueConstraint, Index, JSON,
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


def _uuid() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.utcnow()


# ── 1. platforms ──────────────────────────────────────────────────────────────

class Platform(Base):
    __tablename__ = "platforms"

    id             = Column(String(36), primary_key=True, default=_uuid)
    slug           = Column(String(50), unique=True, nullable=False)
    display_name   = Column(String(100), nullable=False)
    model_name     = Column(String(100), nullable=True)
    api_type       = Column(String(50), nullable=False)     # "server" | "browser"
    retrieval_type = Column(String(50), nullable=False)
    # "model_memory" | "live_retrieval" | "hybrid"
    # Drives gap analysis interpretation:
    #   chatgpt    = model_memory   (answers from training data)
    #   perplexity = live_retrieval (RAG over live web)
    #   gemini     = hybrid
    is_active      = Column(Boolean, default=True)
    created_at     = Column(DateTime, default=_now)
    updated_at     = Column(DateTime, default=_now, onupdate=_now)


# ── 2. query_verticals ────────────────────────────────────────────────────────

class QueryVertical(Base):
    __tablename__ = "query_verticals"

    id           = Column(String(36), primary_key=True, default=_uuid)
    slug         = Column(String(100), unique=True, nullable=False)
    display_name = Column(String(200), nullable=False)
    description  = Column(Text, nullable=True)
    sort_order   = Column(Integer, default=0)
    is_active    = Column(Boolean, default=True)
    created_at   = Column(DateTime, default=_now)
    updated_at   = Column(DateTime, default=_now, onupdate=_now)

    brands  = relationship("Brand", back_populates="vertical")
    panels  = relationship("QueryPanel", back_populates="vertical")


# ── 3. brands ─────────────────────────────────────────────────────────────────

class Brand(Base):
    __tablename__ = "brands"

    id                       = Column(String(36), primary_key=True, default=_uuid)
    canonical_name           = Column(String(200), unique=True, nullable=False)
    slug                     = Column(String(200), unique=True, nullable=False)
    aliases                  = Column(JSON, default=list)
    # ["SFDC", "Salesforce CRM"] — drives rule-based matching
    domain                   = Column(String(200), nullable=True)
    vertical_id              = Column(String(36), ForeignKey("query_verticals.id",
                                    ondelete="SET NULL"), nullable=True)
    additional_verticals     = Column(JSON, default=list)
    source                   = Column(String(50), default="dictionary")
    # "dictionary" | "llm_extracted" | "manual"
    is_verified              = Column(Boolean, default=False)
    # llm_extracted brands start unverified; excluded from public index until True

    # Denormalised cross-platform summary — updated after each run.
    # Enables fast public index reads without joining brand_scores.
    platform_citation_summary = Column(JSON, default=dict)
    # {
    #   "chatgpt":    {"score": 72.0, "rank": 3, "run_date": "2026-03-04"},
    #   "perplexity": {"score": 31.0, "rank": 14, "run_date": "2026-03-04"},
    #   "gemini":     {"score": 55.0, "rank": 8,  "run_date": "2026-03-04"},
    #   "latest_archetype": "training_dependent"
    # }

    latest_archetype         = Column(String(50), nullable=True)
    # Denormalised from most recent ArchetypeSnapshot

    metadata_json            = Column(JSON, default=dict)
    created_at               = Column(DateTime, default=_now)
    updated_at               = Column(DateTime, default=_now, onupdate=_now)

    vertical            = relationship("QueryVertical", back_populates="brands")
    mentions            = relationship("BrandMention", back_populates="brand",
                            cascade="all, delete-orphan")
    scores              = relationship("BrandScore", back_populates="brand",
                            cascade="all, delete-orphan")
    archetype_snapshots = relationship("ArchetypeSnapshot", back_populates="brand",
                            cascade="all, delete-orphan")


# ── 4. brand_dictionary ───────────────────────────────────────────────────────

class BrandDictionaryEntry(Base):
    __tablename__ = "brand_dictionary"

    id          = Column(String(36), primary_key=True, default=_uuid)
    vertical_id = Column(String(36), ForeignKey("query_verticals.id",
                    ondelete="CASCADE"), nullable=False)
    brand_id    = Column(String(36), ForeignKey("brands.id",
                    ondelete="SET NULL"), nullable=True)
    term        = Column(String(200), nullable=False)
    # The exact string to match (canonical name or alias)
    is_alias    = Column(Boolean, default=False)
    created_at  = Column(DateTime, default=_now)

    __table_args__ = (UniqueConstraint("vertical_id", "term"),)


# ── 5. query_panels ───────────────────────────────────────────────────────────

class QueryPanel(Base):
    __tablename__ = "query_panels"

    id                       = Column(String(36), primary_key=True, default=_uuid)
    name                     = Column(String(200), nullable=False)
    slug                     = Column(String(200), unique=True, nullable=False)
    version                  = Column(String(50), nullable=False, default="1.0")
    description              = Column(Text, nullable=True)
    vertical_id              = Column(String(36), ForeignKey("query_verticals.id",
                                    ondelete="SET NULL"), nullable=True)
    query_count              = Column(Integer, default=0)
    is_active                = Column(Boolean, default=True)
    is_baseline_run_complete = Column(Boolean, default=False)
    rerun_cadence_days       = Column(Integer, default=30)
    next_run_at              = Column(DateTime, nullable=True)
    # Gap analysis requires all 3 platforms. This flag enforces it.
    requires_all_platforms   = Column(Boolean, default=True)
    created_at               = Column(DateTime, default=_now)
    updated_at               = Column(DateTime, default=_now, onupdate=_now)

    vertical = relationship("QueryVertical", back_populates="panels")
    queries  = relationship("PanelQuery", back_populates="panel",
                 cascade="all, delete-orphan", order_by="PanelQuery.sort_order")
    runs     = relationship("QueryRun", back_populates="panel",
                 cascade="all, delete-orphan")


# ── 6. panel_queries ──────────────────────────────────────────────────────────

class PanelQuery(Base):
    __tablename__ = "panel_queries"

    id          = Column(String(36), primary_key=True, default=_uuid)
    panel_id    = Column(String(36), ForeignKey("query_panels.id",
                    ondelete="CASCADE"), nullable=False)
    vertical_id = Column(String(36), ForeignKey("query_verticals.id",
                    ondelete="SET NULL"), nullable=True)
    query_text  = Column(Text, nullable=False)
    intent_type = Column(String(50), nullable=False)
    # "recommendation"|"best_for"|"comparison"|"category_open"|"temporal"
    # temporal queries amplify training vs retrieval split most clearly
    bias_flag   = Column(Boolean, default=False)
    # True for queries where platform self-interest affects results
    # (e.g. "ChatGPT vs Claude" asked to ChatGPT). Excluded from archetype scoring.
    sort_order  = Column(Integer, default=0)
    is_active   = Column(Boolean, default=True)
    notes       = Column(Text, nullable=True)
    created_at  = Column(DateTime, default=_now)
    updated_at  = Column(DateTime, default=_now, onupdate=_now)

    panel    = relationship("QueryPanel", back_populates="queries")
    vertical = relationship("QueryVertical")
    results  = relationship("RunResult", back_populates="panel_query",
                 cascade="all, delete-orphan")


# ── 7. query_runs ─────────────────────────────────────────────────────────────

class QueryRun(Base):
    __tablename__ = "query_runs"

    id                           = Column(String(36), primary_key=True, default=_uuid)
    panel_id                     = Column(String(36), ForeignKey("query_panels.id",
                                        ondelete="CASCADE"), nullable=False)
    label                        = Column(String(200), nullable=True)
    is_baseline                  = Column(Boolean, default=False)
    run_date                     = Column(DateTime, default=_now)
    status                       = Column(String(50), default="pending")
    # "pending"|"running"|"complete"|"failed"|"partial"
    platforms_run                = Column(JSON, default=list)

    # Archetype classification is only valid when all 3 platforms completed.
    # If any platform fails, gap_analysis_valid stays False and
    # archetype classification is skipped for this run.
    gap_analysis_valid           = Column(Boolean, default=False)

    total_queries                = Column(Integer, default=0)
    completed_queries            = Column(Integer, default=0)
    failed_queries               = Column(Integer, default=0)

    # Pipeline completion flags — each step sets its flag when done
    extraction_complete          = Column(Boolean, default=False)
    scoring_complete             = Column(Boolean, default=False)
    archetype_complete           = Column(Boolean, default=False)
    index_built                  = Column(Boolean, default=False)
    report_generated             = Column(Boolean, default=False)

    triggered_by                 = Column(String(50), default="manual")
    # "manual" | "scheduler"

    # Version of ARCHETYPE_THRESHOLDS used for this run.
    # Stored so historical runs remain interpretable if thresholds change.
    archetype_threshold_version  = Column(String(20), nullable=True)

    run_notes   = Column(Text, nullable=True)
    created_at  = Column(DateTime, default=_now)
    updated_at  = Column(DateTime, default=_now, onupdate=_now)

    panel   = relationship("QueryPanel", back_populates="runs")
    results = relationship("RunResult", back_populates="run",
                cascade="all, delete-orphan")


# ── 8. run_results ────────────────────────────────────────────────────────────

class RunResult(Base):
    __tablename__ = "run_results"

    id                = Column(String(36), primary_key=True, default=_uuid)
    run_id            = Column(String(36), ForeignKey("query_runs.id",
                            ondelete="CASCADE"), nullable=False)
    panel_query_id    = Column(String(36), ForeignKey("panel_queries.id",
                            ondelete="CASCADE"), nullable=False)
    platform_id       = Column(String(36), ForeignKey("platforms.id",
                            ondelete="CASCADE"), nullable=False)
    query_text        = Column(Text, nullable=False)
    # Snapshot at run time — panel edits don't corrupt historical responses
    response_text     = Column(Text, nullable=True)
    response_tokens   = Column(Integer, nullable=True)
    cited_urls        = Column(JSON, default=list)
    status            = Column(String(50), default="pending")
    # "pending"|"complete"|"failed"|"skipped"
    error_message     = Column(Text, nullable=True)
    latency_ms        = Column(Integer, nullable=True)
    extraction_status = Column(String(50), default="pending")
    # "pending"|"rule_pass_done"|"llm_pass_done"|"complete"|"failed"
    executed_at       = Column(DateTime, nullable=True)
    created_at        = Column(DateTime, default=_now)
    updated_at        = Column(DateTime, default=_now, onupdate=_now)

    run         = relationship("QueryRun", back_populates="results")
    panel_query = relationship("PanelQuery", back_populates="results")
    platform    = relationship("Platform")
    mentions    = relationship("BrandMention", back_populates="result",
                    cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("run_id", "panel_query_id", "platform_id"),
    )


# ── 9. brand_mentions ─────────────────────────────────────────────────────────

class BrandMention(Base):
    """
    Core fact table. One row per brand detected per RunResult.
    run_id and platform_id are denormalised to avoid joins in aggregation queries.
    """
    __tablename__ = "brand_mentions"

    id               = Column(String(36), primary_key=True, default=_uuid)
    result_id        = Column(String(36), ForeignKey("run_results.id",
                            ondelete="CASCADE"), nullable=False)
    brand_id         = Column(String(36), ForeignKey("brands.id",
                            ondelete="CASCADE"), nullable=False)
    run_id           = Column(String(36), ForeignKey("query_runs.id",
                            ondelete="CASCADE"), nullable=False)
    platform_id      = Column(String(36), ForeignKey("platforms.id",
                            ondelete="CASCADE"), nullable=False)
    mention_position = Column(Integer, nullable=False)   # 1 = first brand mentioned
    mention_text     = Column(String(500), nullable=True) # exact text span
    mention_type     = Column(String(50), nullable=False, default="mentioned")
    # "recommended"|"compared"|"mentioned"|"cautioned_against"
    # v1 scoring does not differentiate by type — all score equally.
    # Stored for future sentiment-weighted scoring.
    url_cited        = Column(Boolean, default=False)
    cited_url        = Column(String(500), nullable=True)
    extraction_method = Column(String(50), nullable=False, default="rule")
    # "rule" | "llm"
    confidence       = Column(Float, default=1.0)
    # 1.0 for rule-based; ~0.85 for LLM-extracted
    created_at       = Column(DateTime, default=_now)

    result   = relationship("RunResult", back_populates="mentions")
    brand    = relationship("Brand", back_populates="mentions")
    platform = relationship("Platform")


# ── 10. brand_scores ──────────────────────────────────────────────────────────

class BrandScore(Base):
    """
    Aggregated citation score per brand × platform × vertical × run.
    Includes cross-platform delta fields for gap analysis.
    Delta fields are null until all platform scores for a run are written.
    """
    __tablename__ = "brand_scores"

    id                          = Column(String(36), primary_key=True, default=_uuid)
    run_id                      = Column(String(36), ForeignKey("query_runs.id",
                                        ondelete="CASCADE"), nullable=False)
    brand_id                    = Column(String(36), ForeignKey("brands.id",
                                        ondelete="CASCADE"), nullable=False)
    platform_id                 = Column(String(36), ForeignKey("platforms.id",
                                        ondelete="CASCADE"), nullable=False)
    vertical_id                 = Column(String(36), ForeignKey("query_verticals.id",
                                        ondelete="SET NULL"), nullable=True)
    # null = cross-vertical aggregate

    # Raw counts
    total_mentions              = Column(Integer, default=0)
    queries_cited_in            = Column(Integer, default=0)
    first_position_count        = Column(Integer, default=0)
    url_cited_count             = Column(Integer, default=0)

    # Scores
    citation_score              = Column(Float, default=0.0)
    # Position-weighted: pos1=5, pos2=3, pos3=2, pos4+=1, url_cited=+2
    citation_score_normalised   = Column(Float, default=0.0)
    # Normalised 0-100 within platform × vertical × run
    rank                        = Column(Integer, nullable=True)

    # Baseline delta
    baseline_run_id             = Column(String(36), ForeignKey("query_runs.id",
                                        ondelete="SET NULL"), nullable=True)
    delta_citation_score        = Column(Float, nullable=True)
    delta_rank                  = Column(Integer, nullable=True)
    is_new_entry                = Column(Boolean, default=False)

    # Cross-platform deltas — the gap analysis core
    # Denormalised snapshots avoid a self-join on every archetype computation
    chatgpt_score_this_run      = Column(Float, nullable=True)
    perplexity_score_this_run   = Column(Float, nullable=True)
    gemini_score_this_run       = Column(Float, nullable=True)

    perplexity_vs_chatgpt_delta = Column(Float, nullable=True)
    # perplexity - chatgpt: positive = retrieval_driven, negative = training_dependent
    perplexity_vs_gemini_delta  = Column(Float, nullable=True)
    chatgpt_vs_gemini_delta     = Column(Float, nullable=True)

    platform_variance           = Column(Float, nullable=True)
    # stdev([chatgpt, perplexity, gemini])
    # Low = consistent (consensus candidate), High = divergent

    computed_at = Column(DateTime, default=_now)
    created_at  = Column(DateTime, default=_now)
    updated_at  = Column(DateTime, default=_now, onupdate=_now)

    run      = relationship("QueryRun", foreign_keys=[run_id])
    brand    = relationship("Brand", back_populates="scores")
    platform = relationship("Platform")
    vertical = relationship("QueryVertical")

    __table_args__ = (
        UniqueConstraint("run_id", "brand_id", "platform_id", "vertical_id"),
    )


# ── 11. archetype_snapshots ───────────────────────────────────────────────────

class ArchetypeSnapshot(Base):
    """
    One row per brand × run × vertical.
    Enables longitudinal archetype tracking — is a training_dependent brand's
    Perplexity score rising? Is a ghost brand fading further?
    archetype_threshold_version is stored here AND on QueryRun so historical
    snapshots remain interpretable after threshold changes.
    """
    __tablename__ = "archetype_snapshots"

    id                          = Column(String(36), primary_key=True, default=_uuid)
    run_id                      = Column(String(36), ForeignKey("query_runs.id",
                                        ondelete="CASCADE"), nullable=False)
    brand_id                    = Column(String(36), ForeignKey("brands.id",
                                        ondelete="CASCADE"), nullable=False)
    vertical_id                 = Column(String(36), ForeignKey("query_verticals.id",
                                        ondelete="SET NULL"), nullable=True)
    run_date                    = Column(DateTime, nullable=False)
    # Denormalised — enables time-series queries without joining query_runs

    # Classification
    citation_archetype          = Column(String(50), nullable=False)
    # "training_dependent"|"retrieval_driven"|"consensus_dominant"
    # |"consensus_geo"|"ghost"|"unclassified"
    archetype_confidence        = Column(Float, nullable=False)
    # 0-1: how far scores exceed the threshold, not model certainty
    archetype_signals           = Column(JSON, nullable=False)
    # Exact values that drove classification — stored for auditability
    # and public methodology display. Public subset only (no thresholds).
    archetype_threshold_version = Column(String(20), nullable=False)

    # Trend
    previous_archetype          = Column(String(50), nullable=True)
    archetype_changed           = Column(Boolean, default=False)

    # Denormalised score snapshot
    chatgpt_score               = Column(Float, nullable=True)
    perplexity_score            = Column(Float, nullable=True)
    gemini_score                = Column(Float, nullable=True)
    platform_variance           = Column(Float, nullable=True)

    created_at = Column(DateTime, default=_now)

    run      = relationship("QueryRun")
    brand    = relationship("Brand", back_populates="archetype_snapshots")
    vertical = relationship("QueryVertical")

    __table_args__ = (
        UniqueConstraint("run_id", "brand_id", "vertical_id"),
        Index("ix_archetype_trend", "brand_id", "vertical_id", "run_date"),
    )


# ── 12. citation_index ────────────────────────────────────────────────────────

class CitationIndex(Base):
    """
    Materialised public index snapshot. Rebuilt after each run.
    The WordPress leaderboard page reads from this table via the JSON export.
    Archetype fields only populated when gap_analysis_valid = True for the run.
    """
    __tablename__ = "citation_index"

    id                          = Column(String(36), primary_key=True, default=_uuid)
    index_type                  = Column(String(50), nullable=False)
    # "brand" | "city" | "person" | "publication" — extensible
    platform_slug               = Column(String(50), nullable=False)
    # "chatgpt" | "perplexity" | "gemini" | "all"
    vertical_slug               = Column(String(100), nullable=True)
    run_id                      = Column(String(36), ForeignKey("query_runs.id",
                                        ondelete="CASCADE"), nullable=False)
    index_date                  = Column(Date, nullable=False)
    rank                        = Column(Integer, nullable=False)

    # Entity
    entity_id                   = Column(String(36), nullable=False)
    # Polymorphic FK by index_type — brands.id, cities.id etc.
    entity_name                 = Column(String(200), nullable=False)
    entity_slug                 = Column(String(200), nullable=False)

    # Scores
    citation_score              = Column(Float, default=0.0)
    citation_score_normalised   = Column(Float, default=0.0)
    total_mentions              = Column(Integer, default=0)
    queries_cited_in            = Column(Integer, default=0)
    url_cited_count             = Column(Integer, default=0)
    first_position_count        = Column(Integer, default=0)

    # Trend vs baseline
    delta_rank                  = Column(Integer, nullable=True)
    is_new_entry                = Column(Boolean, default=False)
    trend_direction             = Column(String(20), nullable=True)
    # "rising"|"stable"|"declining"|"new"|"dropped_out"

    # Archetype (cross-platform rows only, gap_analysis_valid required)
    citation_archetype          = Column(String(50), nullable=True)
    archetype_confidence        = Column(Float, nullable=True)
    archetype_signals           = Column(JSON, nullable=True)
    # Public-facing subset — no internal threshold values
    archetype_label_public      = Column(String(100), nullable=True)
    # e.g. "👑 Dominant Brand" — denormalised for fast display

    # Cross-platform scores (denormalised for public comparison tables)
    chatgpt_score               = Column(Float, nullable=True)
    perplexity_score            = Column(Float, nullable=True)
    gemini_score                = Column(Float, nullable=True)
    platform_variance           = Column(Float, nullable=True)
    perplexity_vs_chatgpt_delta = Column(Float, nullable=True)

    created_at = Column(DateTime, default=_now)

    run = relationship("QueryRun")

    __table_args__ = (
        UniqueConstraint("index_type", "platform_slug", "vertical_slug",
                         "run_id", "rank"),
        Index("ix_citation_index_lookup",
              "index_type", "platform_slug", "vertical_slug", "index_date"),
        Index("ix_citation_index_archetype",
              "index_type", "vertical_slug", "citation_archetype", "index_date"),
    )


# ── 13. extraction_runs ───────────────────────────────────────────────────────

class ExtractionRun(Base):
    """Audit log for brand extraction pipeline jobs."""
    __tablename__ = "extraction_runs"

    id                    = Column(String(36), primary_key=True, default=_uuid)
    query_run_id          = Column(String(36), ForeignKey("query_runs.id",
                                ondelete="CASCADE"), nullable=False)
    pass_type             = Column(String(20), nullable=False)  # "rule" | "llm"
    results_processed     = Column(Integer, default=0)
    brands_found          = Column(Integer, default=0)
    new_brands_discovered = Column(Integer, default=0)
    aliases_added         = Column(Integer, default=0)
    errors                = Column(Integer, default=0)
    duration_seconds      = Column(Float, nullable=True)
    error_log             = Column(JSON, default=list)
    status                = Column(String(50), default="complete")
    # "complete" | "partial" | "failed"
    created_at            = Column(DateTime, default=_now)
