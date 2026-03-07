# GEO Brand Citation Index — Project Context

> **Single source of truth for the project.**
> Last Updated: 2026-03-07 | Version: 1.2

---

## 1. What This Project Does

Monthly tracker measuring which brands ChatGPT, Perplexity, and Gemini recommend — and why the gap between platforms reveals more than any single ranking.

**Monthly workflow:**
1. Run 54 queries (18 queries × 3 platforms) via API
2. Extract brand mentions from responses
3. Score brands by citation prominence
4. Compute cross-platform deltas
5. Classify brands into archetypes
6. Generate blog post, social posts, PDF report, JSON data

**Output:** Blog post + 5 social posts + PDF report + JSON leaderboard data

---

## 2. The Core Insight

- **ChatGPT** answers from training data (months/years old)
- **Perplexity** retrieves from the live web (real-time)
- **Gemini** blends both approaches

The **delta** between platforms reveals whether a brand's AI visibility comes from **memory** or **current relevance**.

---

## 3. Five Brand Archetypes

| Archetype | Signal | Example |
|-----------|--------|---------|
| 👑 **Dominant Brand** | High everywhere, consistent | HubSpot, Salesforce |
| 🧠 **AI Memory Brand** | ChatGPT high, Perplexity lower | Ahrefs, Moz |
| 🔍 **Live Search Brand** | Perplexity high, ChatGPT lower | Claude (+50 delta) |
| 🫥 **Fading Brand** | Moderate ChatGPT, near-zero Perplexity | Legacy tools |
| ⭐ **GEO Outlier** | Consistent, exceeds size expectations | Zoho CRM, Copilot |

---

## 4. Stack

| Component | Purpose |
|-----------|---------|
| Python 3.10+ | Main orchestrator |
| SQLite | Citation data storage |
| OpenAI API | ChatGPT queries |
| Google API | Gemini queries |
| Perplexity API | Live web queries |
| Anthropic API | Content generation (Claude) |
| ReportLab | PDF generation |

---

## 5. File Structure

```
geo-citation-index/
├── run_monthly.py              ← Single entry point
├── app/
│   ├── core/
│   │   ├── config.py           ← Constants, thresholds, weights
│   │   ├── brand_extractor.py  ← Two-pass brand extraction
│   │   ├── citation_scorer.py  ← Scoring, deltas, archetypes
│   │   ├── index_builder.py    ← Materialise citation_index
│   │   └── content_generator.py← Auto-generate content
│   ├── models/
│   │   └── db.py               ← SQLAlchemy models
│   └── services/
│       ├── query_runner.py     ← API query runners
│       └── report_writer.py    ← PDF generation
├── frontend/
│   └── perplexity_runner.html  ← Legacy browser runner
├── knowledge/
│   ├── PROJECT_CONTEXT.md      ← This file
│   ├── session_memory.md       ← Session history
│   └── failure_registry.yml    ← Known failures + fixes
├── docs/                       ← Specs and methodology
├── scripts/                    ← Utility scripts
└── outputs/                    ← Generated reports (gitignored)
```

---

## 6. Environment Variables

```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
GOOGLE_API_KEY=AIza...
GEMINI_MODEL=gemini-2.5-flash
PERPLEXITY_API_KEY=pplx-...
PERPLEXITY_MODEL=sonar-pro
ANTHROPIC_API_KEY=sk-ant-...
```

---

## 7. Quick Start

```bash
# Install
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with API keys

# Seed database (first run only)
python scripts/seed_dictionary.py

# Run monthly
python run_monthly.py
```

---

## 8. Monthly Routine (20 min)

1. `python run_monthly.py` — runs all 54 queries (~20 min)
2. Review `outputs/YYYY-MM/report_YYYY-MM.md`
3. Skim `outputs/YYYY-MM/social_posts_YYYY-MM.txt`
4. Upload JSON to WordPress leaderboard
5. Publish report, schedule social posts

---

## 9. Key Links

- **GitHub:** https://github.com/arturseo-geo/geo-citation-index
- **Website:** https://thegeolab.net/geo-brand-citation-index/
- **Local Path:** `C:\Users\jorge\Desktop\GEO Citation Index`

---

## 10. 12-Month Goal

Become what **Ahrefs is for backlinks** — but for **AI citation data**.

First mover with longitudinal data. When someone asks "where do I find AI brand citation data?" → thegeolab.net

---

## 11. First Run Results (March 2026)

- **Run ID:** 494f9bf0-17ed-4f23-8bbc-13e70dcd4bb8
- **Queries:** 54 total (18 × 3 platforms)
- **Brands found:** 392 mentions | 62 new brands discovered
- **Gap analysis:** Valid (cross-platform deltas computed)

**Key Findings:**
| Archetype | Brand | Delta |
|-----------|-------|-------|
| Dominant | ChatGPT, Salesforce, HubSpot | 100% consistent |
| Live Search | Claude | +50 (Perplexity > ChatGPT) |
| Fading | Moz | -44 (ChatGPT > Perplexity) |
| AI Memory | Ahrefs | -48 |
| GEO Outlier | Copilot, Zoho CRM | Consistent across all |

---

## 12. CI/CD Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `docs-integrity.yml` | Push/PR to main | Validates endpoint and model coverage in docs |

**Docs Integrity Check:**
- Compares routes in `app/backend/main.py` with `docs/appendices/endpoint-index.md`
- Compares models in `app/models/db.py` with `docs/appendices/model-index.md`
- Currently: No API layer yet, so endpoint check passes with empty set
- Model coverage: 13 models tracked

---

**Maintained By:** Claude Code
**Version:** 1.2
