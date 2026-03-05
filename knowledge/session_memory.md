# GEO Citation Index - Session Memory

Last Updated: 2026-03-05

---

## Project Overview

**Purpose:** Monthly tracker measuring which brands AI systems (ChatGPT, Perplexity, Gemini) recommend — and why the gap between platforms reveals more than any single ranking.

**GitHub:** https://github.com/arturseo-geo/geo-citation-index

**Local Path:** `C:\Users\jorge\Desktop\GEO Citation Index`

---

## Core Concept

### The Problem
When you ask AI "what's the best CRM?" it names specific brands and ignores others. Nobody currently publishes systematic data on which brands get cited, how consistently, or whether that's changing.

### The Insight
- **ChatGPT** answers from training data (months/years old)
- **Perplexity** retrieves from the live web (real-time)
- Comparing their answers reveals whether a brand's AI visibility comes from **memory** or **current relevance**
- This **delta** is the unique research contribution

---

## Five Brand Archetypes

| Archetype | Signal | Example |
|-----------|--------|---------|
| 👑 **Dominant Brand** | High everywhere, consistent across all platforms | HubSpot for CRM |
| 🧠 **AI Memory Brand** | ChatGPT high, Perplexity lower | Mailchimp (trained on years of dominance) |
| 🔍 **Live Search Brand** | Perplexity high, ChatGPT lower | Klaviyo (strong live web presence) |
| 🫥 **Fading Brand** | Moderate ChatGPT, near-zero Perplexity | Legacy tools AI remembers but web moved on |
| ⭐ **GEO Outlier** | Consistent but exceeds size expectations | Evidence of deliberate GEO strategy working |

---

## Architecture

### Database
- **SQLite** (single file, zero maintenance)
- 13 tables defined in `app/models/db.py`

### Core Components

| File | Purpose |
|------|---------|
| `run_monthly.py` | Single entry point — full pipeline, `--dry-run`, `--content-only` |
| `app/core/config.py` | Constants, thresholds, archetype weights, platform defs |
| `app/core/brand_extractor.py` | Two-pass extraction — rule match + LLM fallback |
| `app/core/citation_scorer.py` | Scoring, deltas, archetype classification |
| `app/core/index_builder.py` | Materializes CitationIndex + exports JSON |
| `app/core/content_generator.py` | Generates blog post + 5 social posts via Anthropic API |
| `app/services/query_runner.py` | ChatGPT + Gemini runners; Perplexity merge |
| `app/services/report_writer.py` | PDF generation via ReportLab |
| `scripts/seed_dictionary.py` | One-time DB setup — platforms, verticals, brands, queries |

### Frontend
- `frontend/perplexity_runner.html` — Browser-based Perplexity query interface

---

## Monthly Process (30 min/month)

| Task | Time | What |
|------|------|------|
| Run script | 2 min active, ~40 min passive | `python run_monthly.py` |
| Review report | 10-15 min | Check narrative, add commentary |
| Review social | 5 min | Skim 5 auto-generated posts |
| Publish | 5 min | Paste to WordPress, upload PDF/JSON |
| Schedule social | 5 min | Paste to Buffer/LinkedIn |

---

## Output Per Month

1. **Blog Post** — Full report with rankings, deltas, archetype findings
2. **Leaderboard Page** — JSON-powered live rankings on thegeolab.net
3. **5 Social Posts** — Auto-generated for LinkedIn/Twitter
4. **PDF Report** — Downloadable, shareable, citable
5. **JSON Data** — For website leaderboard auto-update

---

## File Structure

```
geo-citation-index/
├── app/
│   ├── core/           # Brand extraction, scoring, content gen
│   ├── models/         # SQLAlchemy DB models
│   └── services/       # Query runners, report writer
├── docs/
│   ├── appendices/     # endpoint-index, model-index
│   ├── methodology.md
│   └── *.md            # Specs and strategic review
├── frontend/           # Perplexity runner HTML
├── knowledge/          # failure_registry.yml, session_memory
├── scripts/            # seed_dictionary, check_docs_integrity
├── tests/              # pytest tests
├── run_monthly.py      # Main entry point
├── requirements.txt
└── .env.example
```

---

## API Keys Required

| Service | Purpose |
|---------|---------|
| `OPENAI_API_KEY` | ChatGPT queries |
| `GOOGLE_API_KEY` | Gemini queries |
| `ANTHROPIC_API_KEY` | Content generation (Claude) |

Perplexity: Browser-based via `perplexity_runner.html` (no API key)

---

## CI/CD Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `docs-integrity.yml` | PR to main | Validates docs structure |
| `pr-failure-registry-guard.yml` | PR to main | Ensures failure registry updated |

---

## 12-Month Goal

Become what **Ahrefs is for backlinks** — but for **AI citation data**.

- First mover with longitudinal data
- When someone asks "where do I find AI brand citation data?" → thegeolab.net
- The index builds the brand that builds the index (self-referential authority)

---

## Key Links

- **GitHub:** https://github.com/arturseo-geo/geo-citation-index
- **Briefing:** `C:\Users\jorge\Downloads\geo-citation-index-briefing.html`
- **Website (future):** thegeolab.net/geo-brand-citation-index/

---

## Session History

### 2026-03-05 — Initial Setup
- Extracted project from zip to `C:\Users\jorge\Desktop\GEO Citation Index`
- Initialized git, pushed to GitHub `arturseo-geo/geo-citation-index`
- 41 files, 7433 lines of code
- Created session memory

---
