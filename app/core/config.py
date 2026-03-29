"""
Central configuration for the GEO Citation Index.

All constants, weights, thresholds, and platform definitions live here.
When ARCHETYPE_THRESHOLD_VERSION is bumped, historical snapshots remain
interpretable because the version is stored on every ArchetypeSnapshot row.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── API keys ─────────────────────────────────────────────────────────────────
OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL     = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
GOOGLE_API_KEY   = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL     = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY", "")
PERPLEXITY_MODEL   = os.getenv("PERPLEXITY_MODEL", "sonar")

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///citation_index.db")

# ── Extraction ────────────────────────────────────────────────────────────────
MIN_BRANDS_RULE_PASS        = 3     # LLM pass skipped if rule pass finds >= this many brands
LLM_EXTRACTION_MODEL        = "claude-sonnet-4-20250514"
LLM_EXTRACTION_CONFIDENCE   = 0.85  # Confidence for LLM-extracted mentions
RULE_EXTRACTION_CONFIDENCE  = 1.0   # Confidence for dictionary matches
MAX_BRANDS_PER_RESPONSE     = 20    # Hard cap — prevent runaway extraction

# ── Citation scoring ──────────────────────────────────────────────────────────
POSITION_WEIGHTS = {1: 5, 2: 3, 3: 2}
POSITION_WEIGHT_DEFAULT = 1   # position 4 and beyond
URL_CITED_BONUS = 2           # added when the brand's URL was also cited

# ── Gemini rate limiting ──────────────────────────────────────────────────────
GEMINI_RATE_LIMIT_DELAY_SECONDS = 4  # Free tier: 15 req/min → 4s between requests

# ── Archetype classification ──────────────────────────────────────────────────
# Version MUST be bumped when any threshold value changes.
# Stored on QueryRun and ArchetypeSnapshot rows so historical data
# remains interpretable even after threshold changes.
ARCHETYPE_THRESHOLD_VERSION = "1.0"

# Thresholds match published methodology at
# thegeolab.net/geo-brand-citation-index/methodology/ (Section 7)
ARCHETYPE_THRESHOLDS = {
    "consensus_dominant": {
        "all_platforms_min": 60,       # High scores (60+) on all three platforms
        "platform_variance_max": 15,   # Delta within ±15
    },
    "training_dependent": {
        "chatgpt_min": 0,             # Any ChatGPT score
        "perplexity_vs_chatgpt_delta_max": -20,  # Delta -20 or lower
    },
    "ghost": {
        "chatgpt_min": 10,            # Meaningful ChatGPT presence
        "perplexity_max": 5,          # Near-zero live web presence
        "perplexity_vs_chatgpt_delta_max": -10,  # Must have negative delta
    },
    "retrieval_driven": {
        "perplexity_min": 0,          # Any Perplexity score
        "perplexity_vs_chatgpt_delta_min": 15,  # Delta +15 or above
    },
    "consensus_geo": {
        "all_platforms_min": 25,       # Consistent above prediction
        "all_platforms_max": 60,
        "platform_variance_max": 15,
    },
}

# Classification priority order — first match wins
# training_dependent before ghost: Memory is more actionable than Fading
ARCHETYPE_PRIORITY = [
    "consensus_dominant",
    "training_dependent",
    "ghost",
    "retrieval_driven",
    "consensus_geo",
]

# Public-facing labels (used in reports and social posts)
ARCHETYPE_PUBLIC_LABELS = {
    "consensus_dominant":  "👑 Dominant Brand",
    "ghost":               "🫥 Fading Brand",
    "training_dependent":  "🧠 AI Memory Brand",
    "retrieval_driven":    "🔍 Live Search Brand",
    "consensus_geo":       "⭐ GEO Outlier",
    "unclassified":        "—",
}

# ── Index retention ───────────────────────────────────────────────────────────
MAX_CITATION_INDEX_SNAPSHOTS = 13   # Keep last 13 runs in citation_index table

# ── Output paths ──────────────────────────────────────────────────────────────
OUTPUTS_DIR = "outputs"

# ── Perplexity local server ───────────────────────────────────────────────────
PERPLEXITY_LOCAL_PORT = 5679        # Local HTTP server to receive Perplexity results
PERPLEXITY_TIMEOUT_SECONDS = 600    # 10 min max wait for browser queries to complete

# ── Platforms (seed data) ─────────────────────────────────────────────────────
PLATFORMS = [
    {
        "slug": "chatgpt",
        "display_name": "ChatGPT",
        "model_name": OPENAI_MODEL,
        "api_type": "server",
        "retrieval_type": "model_memory",
    },
    {
        "slug": "perplexity",
        "display_name": "Perplexity",
        "model_name": PERPLEXITY_MODEL,
        "api_type": "server",
        "retrieval_type": "live_retrieval",
    },
    {
        "slug": "gemini",
        "display_name": "Gemini",
        "model_name": GEMINI_MODEL,
        "api_type": "server",
        "retrieval_type": "hybrid",
    },
]

# ── Verticals (v1 scope — 3 verticals) ───────────────────────────────────────
VERTICALS = [
    {
        "slug": "seo-marketing",
        "display_name": "SEO & Marketing Tools",
        "sort_order": 1,
    },
    {
        "slug": "crm-sales",
        "display_name": "CRM & Sales",
        "sort_order": 2,
    },
    {
        "slug": "ai-llm-tools",
        "display_name": "AI & LLM Tools",
        "sort_order": 3,
    },
]
