# GEO Citation Index — Database Models Spec
# Version: 0.2 (revised to incorporate archetype classification layer)

Status: Draft
Author: AJ / The GEO Lab
Last updated: 2026-03-05
Pattern reference: GEO-OS `app/models/db.py` (SQLAlchemy, PostgreSQL-first, UUID PKs)

Changelog from v0.1:
  - Added cross-platform delta fields to `brand_scores`
  - Added `citation_archetype`, `archetype_confidence`, `archetype_signals`
    to `citation_index`
  - Added `platform_citation_summary` to `brands` for fast cross-platform lookup
  - Added `ArchetypeSnapshot` table for longitudinal archetype tracking
  - Added `temporal` intent type to query panel intent definitions
  - Clarified `citation_index` polymorphic design for future entity types

---

## Design Principles

- PostgreSQL primary target. Concurrent scheduler writes make SQLite unsuitable.
- UUID primary keys throughout — same as GEO-OS.
- `created_at` / `updated_at` on every table — same as GEO-OS.
- JSON columns for flexible detail storage — same as GEO-OS.
- Normalised core, JSON for variable payloads (LLM responses, extraction detail).
- No application logic in models. All scoring, delta calculation, and archetype
  classification stays in `app/core/`.
- Foreign keys with explicit `ondelete` behaviour on every relationship.
- Gap analysis is a first-class concern: delta fields and archetype classification
  are not supplemental — they are core output of every run.

---

## Entity Relationship Overview

```
QueryPanel
  └── PanelQuery (many)
       └── QueryRun (many — one per panel execution)
            └── RunResult (many — one per query × platform)
                 └── BrandMention (many — one per brand detected)

Brand  ←──────────────────── BrandMention (brand_id FK)
  └── BrandScore (aggregated per brand × platform × run)
       └── cross-platform deltas computed here

CitationIndex      ← materialised snapshot with archetype classification
ArchetypeSnapshot  ← longitudinal archetype tracking per brand × run

Platform           ← reference table
QueryVertical      ← reference table
BrandDictionary    ← seed brand list per vertical
ExtractionRun      ← audit log for extraction jobs
```

---

## Archetype Classification Overview

Every brand in every run is classified into one of five archetypes based on
its normalised citation scores across platforms and their variance.

| Archetype | Signal Pattern | What It Means |
|-----------|---------------|---------------|
| `training_dependent` | ChatGPT high, Perplexity significantly lower | Citation from model memory, not live retrieval |
| `retrieval_driven` | Perplexity high, ChatGPT lower | Strong live web signals, lower training data saturation |
| `consensus_dominant` | All platforms high, low variance | Dominant brand — training + retrieval both strong |
| `consensus_geo` | All platforms moderate, low variance, low backlinks | Possible GEO success story — consistent without authority |
| `ghost` | ChatGPT moderate/high, Perplexity very low | In model memory, absent from live web |
| `unclassified` | Does not meet any threshold | Insufficient data or borderline signals |

Classification thresholds are defined in `app/core/config.py` as
`ARCHETYPE_THRESHOLDS` and must be versioned when changed so historical
snapshots remain interpretable.

---

## Table Specifications

---

### 1. `platforms` — Reference table

```python
class Platform(Base):
    __tablename__ = "platforms"

    id            = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    slug          = Column(String(50), unique=True, nullable=False)
    # "chatgpt" | "perplexity" | "gemini"
    display_name  = Column(String(100), nullable=False)
    model_name    = Column(String(100), nullable=True)
    api_type      = Column(String(50), nullable=False)
    # "server" | "browser"
    retrieval_type = Column(String(50), nullable=False)
    # "model_memory" | "live_retrieval" | "hybrid"
    # Critical for gap analysis interpretation:
    #   chatgpt   = model_memory   (no live search by default)
    #   perplexity = live_retrieval (RAG over Bing index)
    #   gemini    = hybrid         (model + Google index)
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

**Seed data:**
| slug | display_name | model_name | api_type | retrieval_type |
|------|-------------|-----------|---------|---------------|
| chatgpt | ChatGPT | gpt-4o-mini | server | model_memory |
| perplexity | Perplexity | sonar | browser | live_retrieval |
| gemini | Gemini | gemini-1.5-flash | server | hybrid |

Note: `retrieval_type` drives how gap analysis interprets divergent scores.
The ChatGPT vs Perplexity delta is the primary diagnostic because those two
represent the clearest model_memory vs live_retrieval contrast.

---

### 2. `query_verticals` — Reference table

```python
class QueryVertical(Base):
    __tablename__ = "query_verticals"

    id            = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    slug          = Column(String(100), unique=True, nullable=False)
    display_name  = Column(String(200), nullable=False)
    description   = Column(Text, nullable=True)
    sort_order    = Column(Integer, default=0)
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

**v1 seed verticals:**
| slug | display_name |
|------|-------------|
| seo-marketing | SEO & Marketing Tools |
| crm-sales | CRM & Sales |
| project-management | Project Management |
| ai-llm-tools | AI & LLM Tools |
| cloud-infrastructure | Cloud & Infrastructure |
| email-marketing | Email Marketing |
| analytics | Analytics & BI |
| hr-recruiting | HR & Recruiting |

---

### 3. `brands` — Master brand registry

```python
class Brand(Base):
    __tablename__ = "brands"

    id                      = Column(String(36), primary_key=True,
                                default=lambda: str(uuid4()))
    canonical_name          = Column(String(200), unique=True, nullable=False)
    slug                    = Column(String(200), unique=True, nullable=False)
    aliases                 = Column(JSON, default=list)
    # ["SFDC", "Salesforce CRM"] — drives rule-based matching
    domain                  = Column(String(200), nullable=True)
    vertical_id             = Column(String(36), ForeignKey("query_verticals.id",
                                ondelete="SET NULL"), nullable=True)
    additional_verticals    = Column(JSON, default=list)
    source                  = Column(String(50), default="dictionary")
    # "dictionary" | "llm_extracted" | "manual"
    is_verified             = Column(Boolean, default=False)

    # Cross-platform summary — denormalised for fast public index reads.
    # Updated by index_builder after each run. Stores latest run's scores.
    platform_citation_summary = Column(JSON, default=dict)
    # Structure:
    # {
    #   "chatgpt":    {"score": 72.0, "rank": 3, "run_date": "2026-03-04"},
    #   "perplexity": {"score": 31.0, "rank": 14, "run_date": "2026-03-04"},
    #   "gemini":     {"score": 55.0, "rank": 8,  "run_date": "2026-03-04"},
    #   "latest_archetype": "training_dependent",
    #   "archetype_updated_at": "2026-03-04"
    # }
    # Enables gap analysis queries without joining brand_scores.

    latest_archetype        = Column(String(50), nullable=True)
    # Denormalised from most recent ArchetypeSnapshot — drives filtering
    # on public index without joining archetype table.

    metadata_json           = Column(JSON, default=dict)
    created_at              = Column(DateTime, default=datetime.utcnow)
    updated_at              = Column(DateTime, default=datetime.utcnow,
                                onupdate=datetime.utcnow)

    vertical                = relationship("QueryVertical", backref="brands")
    mentions                = relationship("BrandMention", back_populates="brand",
                                cascade="all, delete-orphan")
    scores                  = relationship("BrandScore", back_populates="brand",
                                cascade="all, delete-orphan")
    archetype_snapshots     = relationship("ArchetypeSnapshot",
                                back_populates="brand",
                                cascade="all, delete-orphan")
```

---

### 4. `brand_dictionary` — Seed brand list per vertical

```python
class BrandDictionaryEntry(Base):
    __tablename__ = "brand_dictionary"

    id          = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    vertical_id = Column(String(36), ForeignKey("query_verticals.id",
                    ondelete="CASCADE"), nullable=False)
    brand_id    = Column(String(36), ForeignKey("brands.id",
                    ondelete="SET NULL"), nullable=True)
    term        = Column(String(200), nullable=False)
    is_alias    = Column(Boolean, default=False)
    created_at  = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("vertical_id", "term"),
    )
```

---

### 5. `query_panels` — Named, versioned query panels

```python
class QueryPanel(Base):
    __tablename__ = "query_panels"

    id                       = Column(String(36), primary_key=True,
                                 default=lambda: str(uuid4()))
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

    # Gap analysis requires all three platforms on every run.
    # If a platform is excluded, archetype classification is invalid.
    # This flag enforces the constraint at the panel level.
    requires_all_platforms   = Column(Boolean, default=True)

    created_at               = Column(DateTime, default=datetime.utcnow)
    updated_at               = Column(DateTime, default=datetime.utcnow,
                                 onupdate=datetime.utcnow)

    vertical   = relationship("QueryVertical", backref="panels")
    queries    = relationship("PanelQuery", back_populates="panel",
                   cascade="all, delete-orphan", order_by="PanelQuery.sort_order")
    runs       = relationship("QueryRun", back_populates="panel",
                   cascade="all, delete-orphan")
```

---

### 6. `panel_queries` — Individual queries within a panel

```python
class PanelQuery(Base):
    __tablename__ = "panel_queries"

    id          = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    panel_id    = Column(String(36), ForeignKey("query_panels.id",
                    ondelete="CASCADE"), nullable=False)
    vertical_id = Column(String(36), ForeignKey("query_verticals.id",
                    ondelete="SET NULL"), nullable=True)
    query_text  = Column(Text, nullable=False)
    intent_type = Column(String(50), nullable=False)
    # "recommendation" | "best_for" | "comparison" | "category_open" | "temporal"
    # temporal = queries with explicit recency framing
    # ("What are the best CRM tools in 2026?")
    # Key for gap analysis: temporal queries amplify the training vs retrieval split.
    # Brands appearing only on Perplexity for temporal queries but not ChatGPT
    # are strong candidates for retrieval_driven archetype.
    sort_order  = Column(Integer, default=0)
    is_active   = Column(Boolean, default=True)
    notes       = Column(Text, nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    panel    = relationship("QueryPanel", back_populates="queries")
    vertical = relationship("QueryVertical")
    results  = relationship("RunResult", back_populates="panel_query",
                 cascade="all, delete-orphan")
```

**Intent types:**
| intent_type | Example | Gap analysis role |
|-------------|---------|------------------|
| recommendation | "What are the best CRM tools?" | Baseline citation signal |
| best_for | "Best CRM for small business?" | Niche authority signal |
| comparison | "Salesforce vs HubSpot?" | Head-to-head divergence signal |
| category_open | "Which CRM platforms are popular?" | Unprompted association signal |
| temporal | "Best CRM tools in 2026?" | Training cutoff diagnostic |

---

### 7. `query_runs` — One execution of a full panel

```python
class QueryRun(Base):
    __tablename__ = "query_runs"

    id                   = Column(String(36), primary_key=True,
                             default=lambda: str(uuid4()))
    panel_id             = Column(String(36), ForeignKey("query_panels.id",
                             ondelete="CASCADE"), nullable=False)
    label                = Column(String(200), nullable=True)
    is_baseline          = Column(Boolean, default=False)
    run_date             = Column(DateTime, default=datetime.utcnow)
    status               = Column(String(50), default="pending")
    # "pending"|"running"|"complete"|"failed"|"partial"
    platforms_run        = Column(JSON, default=list)
    # ["chatgpt","perplexity","gemini"]

    # Gap analysis validity flag.
    # Set True only when all three platforms have complete results.
    # Archetype classification must not run on partial platform data.
    gap_analysis_valid   = Column(Boolean, default=False)

    total_queries        = Column(Integer, default=0)
    completed_queries    = Column(Integer, default=0)
    failed_queries       = Column(Integer, default=0)
    extraction_complete  = Column(Boolean, default=False)
    scoring_complete     = Column(Boolean, default=False)
    # True once brand_scores computed for this run
    archetype_complete   = Column(Boolean, default=False)
    # True once ArchetypeSnapshot rows written for this run
    index_built          = Column(Boolean, default=False)
    triggered_by         = Column(String(50), default="manual")
    # "manual" | "scheduler"
    run_notes            = Column(Text, nullable=True)

    # Threshold version used for archetype classification.
    # Must be stored so historical runs remain interpretable
    # if thresholds change in config.py.
    archetype_threshold_version = Column(String(20), nullable=True)

    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    panel    = relationship("QueryPanel", back_populates="runs")
    results  = relationship("RunResult", back_populates="run",
                 cascade="all, delete-orphan")
```

---

### 8. `run_results` — One LLM response per query × platform

```python
class RunResult(Base):
    __tablename__ = "run_results"

    id                 = Column(String(36), primary_key=True,
                           default=lambda: str(uuid4()))
    run_id             = Column(String(36), ForeignKey("query_runs.id",
                           ondelete="CASCADE"), nullable=False)
    panel_query_id     = Column(String(36), ForeignKey("panel_queries.id",
                           ondelete="CASCADE"), nullable=False)
    platform_id        = Column(String(36), ForeignKey("platforms.id",
                           ondelete="CASCADE"), nullable=False)
    query_text         = Column(Text, nullable=False)
    # Snapshot at run time — panel edits don't corrupt history
    response_text      = Column(Text, nullable=True)
    response_tokens    = Column(Integer, nullable=True)
    cited_urls         = Column(JSON, default=list)
    status             = Column(String(50), default="pending")
    # "pending"|"complete"|"failed"|"skipped"
    error_message      = Column(Text, nullable=True)
    latency_ms         = Column(Integer, nullable=True)
    extraction_status  = Column(String(50), default="pending")
    # "pending"|"rule_pass_done"|"llm_pass_done"|"complete"|"failed"
    executed_at        = Column(DateTime, nullable=True)
    created_at         = Column(DateTime, default=datetime.utcnow)
    updated_at         = Column(DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    run          = relationship("QueryRun", back_populates="results")
    panel_query  = relationship("PanelQuery", back_populates="results")
    platform     = relationship("Platform")
    mentions     = relationship("BrandMention", back_populates="result",
                     cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("run_id", "panel_query_id", "platform_id"),
    )
```

---

### 9. `brand_mentions` — Extracted brand appearances per result

Core fact table. One row per brand detected per RunResult.

```python
class BrandMention(Base):
    __tablename__ = "brand_mentions"

    id                = Column(String(36), primary_key=True,
                          default=lambda: str(uuid4()))
    result_id         = Column(String(36), ForeignKey("run_results.id",
                          ondelete="CASCADE"), nullable=False)
    brand_id          = Column(String(36), ForeignKey("brands.id",
                          ondelete="CASCADE"), nullable=False)
    run_id            = Column(String(36), ForeignKey("query_runs.id",
                          ondelete="CASCADE"), nullable=False)
    # Denormalised — avoids join through run_results on aggregation queries
    platform_id       = Column(String(36), ForeignKey("platforms.id",
                          ondelete="CASCADE"), nullable=False)
    # Denormalised — same reason
    mention_position  = Column(Integer, nullable=False)
    # 1 = first brand mentioned in response
    mention_text      = Column(String(500), nullable=True)
    # Exact text span for audit
    mention_type      = Column(String(50), nullable=False, default="mentioned")
    # "recommended"|"compared"|"mentioned"|"cautioned_against"
    # Note: v1 scoring does not differentiate by mention_type.
    # All mentions score equally. mention_type is stored for future
    # sentiment-weighted scoring and is a research output in itself.
    url_cited         = Column(Boolean, default=False)
    cited_url         = Column(String(500), nullable=True)
    extraction_method = Column(String(50), nullable=False, default="rule")
    # "rule" | "llm"
    confidence        = Column(Float, default=1.0)
    # 1.0 for rule-based; 0.7-0.95 for LLM-extracted
    created_at        = Column(DateTime, default=datetime.utcnow)

    result   = relationship("RunResult", back_populates="mentions")
    brand    = relationship("Brand", back_populates="mentions")
    platform = relationship("Platform")
```

---

### 10. `brand_scores` — Aggregated citation score per brand × platform × run

Computed after extraction is complete. Now includes cross-platform delta fields
for gap analysis. Delta fields are populated by `citation_scorer.py` after
all platform scores for a run are complete.

```python
class BrandScore(Base):
    __tablename__ = "brand_scores"

    id                         = Column(String(36), primary_key=True,
                                   default=lambda: str(uuid4()))
    run_id                     = Column(String(36), ForeignKey("query_runs.id",
                                   ondelete="CASCADE"), nullable=False)
    brand_id                   = Column(String(36), ForeignKey("brands.id",
                                   ondelete="CASCADE"), nullable=False)
    platform_id                = Column(String(36), ForeignKey("platforms.id",
                                   ondelete="CASCADE"), nullable=False)
    vertical_id                = Column(String(36), ForeignKey("query_verticals.id",
                                   ondelete="SET NULL"), nullable=True)
    # Null = cross-vertical aggregate

    # ── Raw counts ──────────────────────────────────────────────────────────
    total_mentions             = Column(Integer, default=0)
    queries_cited_in           = Column(Integer, default=0)
    first_position_count       = Column(Integer, default=0)
    url_cited_count            = Column(Integer, default=0)

    # ── Citation scores ──────────────────────────────────────────────────────
    # Position-weighted: pos1=5, pos2=3, pos3=2, pos4+=1, url_cited=+2
    citation_score             = Column(Float, default=0.0)
    citation_score_normalised  = Column(Float, default=0.0)
    # Normalised 0-100 within platform × vertical × run
    rank                       = Column(Integer, nullable=True)

    # ── Baseline delta ───────────────────────────────────────────────────────
    baseline_run_id            = Column(String(36), ForeignKey("query_runs.id",
                                   ondelete="SET NULL"), nullable=True)
    delta_citation_score       = Column(Float, nullable=True)
    delta_rank                 = Column(Integer, nullable=True)
    is_new_entry               = Column(Boolean, default=False)

    # ── Cross-platform delta fields (NEW — gap analysis) ──────────────────
    # Populated after all platform scores for this run_id × vertical_id
    # are written. Null if other platform score is missing for this run.

    perplexity_score_this_run  = Column(Float, nullable=True)
    # Denormalised snapshot of Perplexity normalised score for same
    # run × vertical. Avoids self-join when computing deltas.
    chatgpt_score_this_run     = Column(Float, nullable=True)
    gemini_score_this_run      = Column(Float, nullable=True)

    perplexity_vs_chatgpt_delta = Column(Float, nullable=True)
    # perplexity_score - chatgpt_score
    # Positive = higher on Perplexity (retrieval_driven signal)
    # Negative = higher on ChatGPT (training_dependent signal)
    perplexity_vs_gemini_delta  = Column(Float, nullable=True)
    chatgpt_vs_gemini_delta     = Column(Float, nullable=True)

    platform_variance           = Column(Float, nullable=True)
    # Standard deviation of normalised scores across all three platforms.
    # Low variance = consistent (consensus archetype candidate)
    # High variance = divergent (training_dependent or retrieval_driven)

    computed_at = Column(DateTime, default=datetime.utcnow)
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    run      = relationship("QueryRun")
    brand    = relationship("Brand", back_populates="scores")
    platform = relationship("Platform")
    vertical = relationship("QueryVertical")

    __table_args__ = (
        UniqueConstraint("run_id", "brand_id", "platform_id", "vertical_id"),
    )
```

---

### 11. `archetype_snapshots` — Longitudinal archetype classification per brand

One row per brand × run × vertical. Enables trend tracking:
is a training_dependent brand's Perplexity score rising? Is a ghost brand
fading further? Is a consensus brand's variance increasing?

```python
class ArchetypeSnapshot(Base):
    __tablename__ = "archetype_snapshots"

    id                       = Column(String(36), primary_key=True,
                                 default=lambda: str(uuid4()))
    run_id                   = Column(String(36), ForeignKey("query_runs.id",
                                 ondelete="CASCADE"), nullable=False)
    brand_id                 = Column(String(36), ForeignKey("brands.id",
                                 ondelete="CASCADE"), nullable=False)
    vertical_id              = Column(String(36), ForeignKey("query_verticals.id",
                                 ondelete="SET NULL"), nullable=True)
    run_date                 = Column(DateTime, nullable=False)
    # Denormalised — enables time-series queries without joining query_runs

    # ── Classification ───────────────────────────────────────────────────────
    citation_archetype       = Column(String(50), nullable=False)
    # "training_dependent" | "retrieval_driven" | "consensus_dominant"
    # | "consensus_geo" | "ghost" | "unclassified"
    archetype_confidence     = Column(Float, nullable=False)
    # 0.0-1.0. How clearly the brand fits the archetype.
    # Computed from how far each delta exceeds its threshold.
    archetype_signals        = Column(JSON, nullable=False)
    # The exact values that drove classification. Stored for auditability
    # and for public methodology display.
    # Structure:
    # {
    #   "chatgpt_normalised": 72.0,
    #   "perplexity_normalised": 31.0,
    #   "gemini_normalised": 55.0,
    #   "perplexity_vs_chatgpt_delta": -41.0,
    #   "platform_variance": 16.8,
    #   "threshold_version": "1.0",
    #   "primary_signal": "perplexity_vs_chatgpt_delta",
    #   "threshold_met": "training_dependent"
    # }

    archetype_threshold_version = Column(String(20), nullable=False)
    # Version of ARCHETYPE_THRESHOLDS used. Must match query_runs value.
    # Stored here too for direct snapshot-level queries.

    # ── Trend fields ─────────────────────────────────────────────────────────
    previous_archetype       = Column(String(50), nullable=True)
    # Archetype from previous run — null if first run
    archetype_changed        = Column(Boolean, default=False)
    # True if citation_archetype != previous_archetype

    # ── Score snapshot ───────────────────────────────────────────────────────
    # Denormalised from brand_scores for self-contained time-series queries
    chatgpt_score            = Column(Float, nullable=True)
    perplexity_score         = Column(Float, nullable=True)
    gemini_score             = Column(Float, nullable=True)
    platform_variance        = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    run     = relationship("QueryRun")
    brand   = relationship("Brand", back_populates="archetype_snapshots")
    vertical = relationship("QueryVertical")

    __table_args__ = (
        UniqueConstraint("run_id", "brand_id", "vertical_id"),
        Index("ix_archetype_trend",
              "brand_id", "vertical_id", "run_date"),
        # Optimises time-series queries: "all archetype snapshots for brand X
        # in vertical Y ordered by date"
    )
```

---

### 12. `citation_index` — Materialised public index snapshot

Rebuilt after each run. Now includes archetype classification fields.
The Next.js frontend reads from this table directly — no aggregation at
render time.

```python
class CitationIndex(Base):
    __tablename__ = "citation_index"

    id                         = Column(String(36), primary_key=True,
                                   default=lambda: str(uuid4()))
    index_type                 = Column(String(50), nullable=False)
    # "brand" | "city" | "person" | "publication" — extensible
    platform_slug              = Column(String(50), nullable=False)
    # "chatgpt" | "perplexity" | "gemini" | "all"
    vertical_slug              = Column(String(100), nullable=True)
    run_id                     = Column(String(36), ForeignKey("query_runs.id",
                                   ondelete="CASCADE"), nullable=False)
    index_date                 = Column(Date, nullable=False)
    rank                       = Column(Integer, nullable=False)

    # ── Entity fields ────────────────────────────────────────────────────────
    entity_id                  = Column(String(36), nullable=False)
    # FK to brands.id, cities.id etc — polymorphic by index_type
    entity_name                = Column(String(200), nullable=False)
    # Denormalised for fast reads
    entity_slug                = Column(String(200), nullable=False)

    # ── Citation scores ──────────────────────────────────────────────────────
    citation_score             = Column(Float, default=0.0)
    citation_score_normalised  = Column(Float, default=0.0)
    total_mentions             = Column(Integer, default=0)
    queries_cited_in           = Column(Integer, default=0)
    url_cited_count            = Column(Integer, default=0)
    first_position_count       = Column(Integer, default=0)

    # ── Baseline delta ───────────────────────────────────────────────────────
    delta_rank                 = Column(Integer, nullable=True)
    is_new_entry               = Column(Boolean, default=False)
    trend_direction            = Column(String(20), nullable=True)
    # "rising" | "stable" | "declining" | "new" | "dropped_out"

    # ── Archetype classification (NEW) ───────────────────────────────────────
    # Only populated on cross-platform index rows (platform_slug = "all")
    # and on per-platform rows where gap analysis is valid for this run.
    citation_archetype         = Column(String(50), nullable=True)
    # "training_dependent" | "retrieval_driven" | "consensus_dominant"
    # | "consensus_geo" | "ghost" | "unclassified"
    archetype_confidence       = Column(Float, nullable=True)
    archetype_signals          = Column(JSON, nullable=True)
    # Subset of ArchetypeSnapshot.archetype_signals for public display.
    # Does NOT include internal threshold values — public-facing only:
    # {
    #   "chatgpt_score": 72.0,
    #   "perplexity_score": 31.0,
    #   "gemini_score": 55.0,
    #   "primary_signal": "perplexity_vs_chatgpt_delta"
    # }

    # Cross-platform scores denormalised for public comparison tables
    chatgpt_score              = Column(Float, nullable=True)
    perplexity_score           = Column(Float, nullable=True)
    gemini_score               = Column(Float, nullable=True)
    platform_variance          = Column(Float, nullable=True)
    perplexity_vs_chatgpt_delta = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("index_type", "platform_slug", "vertical_slug",
                         "run_id", "rank"),
        Index("ix_citation_index_lookup",
              "index_type", "platform_slug", "vertical_slug", "index_date"),
        Index("ix_citation_index_archetype",
              "index_type", "vertical_slug", "citation_archetype", "index_date"),
        # Optimises archetype-filtered public pages:
        # "show all training_dependent brands in CRM vertical"
    )
```

---

### 13. `extraction_runs` — Audit log for brand extraction pipeline

```python
class ExtractionRun(Base):
    __tablename__ = "extraction_runs"

    id                     = Column(String(36), primary_key=True,
                               default=lambda: str(uuid4()))
    query_run_id           = Column(String(36), ForeignKey("query_runs.id",
                               ondelete="CASCADE"), nullable=False)
    pass_type              = Column(String(20), nullable=False)
    # "rule" | "llm"
    results_processed      = Column(Integer, default=0)
    brands_found           = Column(Integer, default=0)
    new_brands_discovered  = Column(Integer, default=0)
    aliases_added          = Column(Integer, default=0)
    errors                 = Column(Integer, default=0)
    duration_seconds       = Column(Float, nullable=True)
    error_log              = Column(JSON, default=list)
    status                 = Column(String(50), default="complete")
    created_at             = Column(DateTime, default=datetime.utcnow)
```

---

## Scoring and Classification Reference

### Citation Score Formula
Defined in `app/core/citation_scorer.py`:

```python
POSITION_WEIGHTS = {1: 5, 2: 3, 3: 2}
POSITION_WEIGHT_DEFAULT = 1   # position 4+
URL_CITED_BONUS = 2

def compute_citation_score(mentions: list[BrandMention]) -> float:
    score = 0.0
    for m in mentions:
        weight = POSITION_WEIGHTS.get(m.mention_position, POSITION_WEIGHT_DEFAULT)
        score += weight
        if m.url_cited:
            score += URL_CITED_BONUS
    return score
```

### Archetype Thresholds
Defined in `app/core/config.py` as `ARCHETYPE_THRESHOLDS`.
Version must be bumped on any threshold change.

```python
ARCHETYPE_THRESHOLD_VERSION = "1.0"

ARCHETYPE_THRESHOLDS = {
    "training_dependent": {
        "chatgpt_normalised_min": 50,
        "perplexity_vs_chatgpt_delta_max": -20,
        # High ChatGPT score + Perplexity significantly lower
    },
    "retrieval_driven": {
        "perplexity_normalised_min": 40,
        "perplexity_vs_chatgpt_delta_min": 15,
        # Perplexity meaningfully higher than ChatGPT
    },
    "consensus_dominant": {
        "all_platforms_normalised_min": 50,
        "platform_variance_max": 15,
        # Strong and consistent across all three
    },
    "consensus_geo": {
        "all_platforms_normalised_min": 25,
        "all_platforms_normalised_max": 60,
        "platform_variance_max": 15,
        # Consistent but not dominant — possible GEO signal
        # Requires manual backlink review to confirm
    },
    "ghost": {
        "chatgpt_normalised_min": 35,
        "perplexity_normalised_max": 15,
        # Present in model memory, nearly absent from live retrieval
    }
}
# Priority order for classification when multiple thresholds are met:
# consensus_dominant > ghost > training_dependent > retrieval_driven > consensus_geo
# If none met: "unclassified"
```

### Platform Variance Formula

```python
import statistics

def compute_platform_variance(
    chatgpt: float, perplexity: float, gemini: float
) -> float:
    return statistics.stdev([chatgpt, perplexity, gemini])
```

---

## Processing Pipeline Order

After each QueryRun completes:

```
1. extraction_complete = True
   └── brand_mentions rows written for all run_results

2. scoring_complete = True
   └── brand_scores rows written (one per brand × platform × vertical)
   └── cross-platform delta fields computed and written
   └── brand.platform_citation_summary updated

3. archetype_complete = True
   └── ArchetypeSnapshot rows written (one per brand × vertical)
   └── brand.latest_archetype updated

4. gap_analysis_valid = True  (if all 3 platforms complete)

5. index_built = True
   └── citation_index rebuilt from brand_scores + archetype_snapshots
   └── Old snapshots pruned (retain last 13 runs)
   └── Next.js rebuild triggered (or ISR revalidation)
```

---

## Migration Notes

- PostgreSQL only. No SQLite fallback.
- Seed order: `platforms` → `query_verticals` → `brand_dictionary` → `brands`
- `ARCHETYPE_THRESHOLD_VERSION` must be set before first run and stored on
  `query_runs` and `archetype_snapshots` rows.
- One-time seed script: `scripts/seed_dictionary.py`

---

## Future Entity Tables (not in v1)

`CitationIndex.entity_id` is polymorphic by `index_type`. Adding cities,
people, and publications requires only new entity tables — no migration
on `citation_index`, `archetype_snapshots`, or `brand_scores`.

```
cities        ← id, name, slug, country, region
persons       ← id, name, slug, role, organisation_id
publications  ← id, name, slug, domain, media_type
```

Each new entity type gets its own extraction logic but shares the same
scoring, delta, archetype, and index pipeline.
