# GEO Brand Citation Index

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19450361.svg)](https://doi.org/10.5281/zenodo.19450361)

Monthly tracker measuring which brands ChatGPT, Perplexity, and Gemini recommend — and why the gap between platforms tells you more than any single ranking.

Published at [thegeolab.net/geo-brand-citation-index](https://thegeolab.net/geo-brand-citation-index/)

---

## What this is

Every month this system runs 18 queries across three AI platforms (ChatGPT, Perplexity, Gemini) — 54 total API calls — extracts every brand mentioned in the responses, scores each brand by citation prominence, and computes the delta between platforms.

The delta is the finding. ChatGPT answers from training data. Perplexity retrieves from the live web. When a brand scores high on ChatGPT but low on Perplexity, that signals the brand is living on AI memory — known from training, but fading from live relevance.

Every brand is classified into one of five archetypes:

| Label | Signal |
|-------|--------|
| 👑 Dominant Brand | High everywhere, low variance |
| 🧠 AI Memory Brand | High ChatGPT, low Perplexity |
| 🔍 Live Search Brand | High Perplexity, lower ChatGPT |
| 🫥 Fading Brand | Moderate ChatGPT, near-zero Perplexity |
| ⭐ GEO Outlier | Consistent but outperforming predicted authority |

After each run, the pipeline auto-generates a blog post draft, five social media posts, a PDF report, and the index JSON for the leaderboard page.

---

## Quick start

```bash
# 1. Clone
git clone https://github.com/arturseo-geo/geo-citation-index.git
cd geo-citation-index

# 2. Install
pip install -r requirements.txt

# 3. Set API keys
cp .env.example .env
# Edit .env with your OpenAI and Google API keys

# 4. Seed the brand dictionary (first run only)
python scripts/seed_dictionary.py

# 5. Run
python run_monthly.py
```

Output files are written to `outputs/YYYY-MM/`.

---

## Project structure

```
geo-citation-index/
├── run_monthly.py              ← Single entry point
├── app/
│   ├── core/
│   │   ├── config.py           ← Constants, thresholds, weights
│   │   ├── brand_extractor.py  ← Two-pass brand extraction
│   │   ├── citation_scorer.py  ← Scoring, deltas, archetype classification
│   │   ├── index_builder.py    ← Materialise citation_index table
│   │   └── content_generator.py← Auto-generate report + social posts
│   ├── models/
│   │   ├── db.py               ← SQLAlchemy models (SQLite)
│   │   └── db_engine.py        ← DB connection
│   └── services/
│       ├── query_runner.py     ← Runs queries against ChatGPT + Gemini
│       └── report_writer.py    ← PDF generation (ReportLab)
├── frontend/
│   ├── perplexity_runner.html  ← Legacy browser runner (now uses API)
│   └── chatgpt_runner.html     ← Browser-side ChatGPT via Puter.js
├── scripts/
│   ├── seed_dictionary.py      ← One-time brand dictionary seed
│   ├── check_docs_integrity.py ← CI: model coverage check
│   └── auto_push.ps1           ← Windows auto-commit helper
├── knowledge/
│   ├── PROJECT_CONTEXT.md      ← Single source of truth
│   ├── session_memory.md       ← Session history
│   └── failure_registry.yml    ← Known failure modes + validated fixes
├── docs/                       ← Specs and methodology
├── tests/                      ← Unit tests
└── outputs/                    ← Generated reports (gitignored)
```

---

## Environment variables

```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
GOOGLE_API_KEY=AIza...
GEMINI_MODEL=gemini-2.5-flash
PERPLEXITY_API_KEY=pplx-...
PERPLEXITY_MODEL=sonar-pro
ANTHROPIC_API_KEY=sk-ant-...
```

All three platforms (ChatGPT, Gemini, Perplexity) run server-side via API — no browser required.

---

## Monthly routine

1. `python run_monthly.py` — runs all 54 queries across 3 platforms (~20 min)
2. Review `outputs/YYYY-MM/report_YYYY-MM.md` — add one paragraph of commentary
3. Skim `outputs/YYYY-MM/social_posts_YYYY-MM.txt` — adjust tone if needed
4. Upload `outputs/YYYY-MM/index_data_YYYY-MM.json` to WordPress
5. Publish the report, schedule social posts

Total active time: ~20 minutes.

---

## Dry run / content-only mode

```bash
# Validate config without running queries
python run_monthly.py --dry-run

# Regenerate content from last run's data (no new queries)
python run_monthly.py --content-only
```

---

## Tests

```bash
python -m pytest tests/ -v
```

---

## v1 scope

- 3 verticals: SEO & Marketing, CRM & Sales, AI & LLM Tools
- 18 queries, 38 brands (seeded) + discovered brands each run
- 3 platforms: ChatGPT, Perplexity, Gemini

Vertical expansion is planned quarterly — each expansion is a content moment.

**March 2026 First Run Results:**
- 392 brand mentions | 62 new brands discovered
- Key findings: Claude +50 delta (Live Search Brand), Moz -44 delta (Fading Brand)

---

## Docs

- [DB Models](docs/citation-index-db-models-v2.md)
- [Query Panel Design](docs/citation-index-query-panel-v2.md)
- [Brand Extractor & Scorer Spec](docs/citation-index-extractor-scorer-spec.md)
- [Strategic Review](docs/citation-index-strategic-review.md)

---

## CI/CD

| Workflow | Trigger | What it checks |
|----------|---------|----------------|
| Docs Integrity | Push/PR to main | Model and endpoint coverage in docs |

The workflow validates that `docs/appendices/model-index.md` matches the SQLAlchemy models in `app/models/db.py`. When an API layer is added, it will also validate endpoint coverage.

---

## Cite this work

If you use this code or reference the Brand Citation Index methodology, please cite:

- March 2026 run — [10.5281/zenodo.19218296](https://doi.org/10.5281/zenodo.19218296)
- April 2026 run — [10.5281/zenodo.19450361](https://doi.org/10.5281/zenodo.19450361)

BibTeX:

```bibtex
@software{ferreira_geo_citation_index_2026,
  author    = {Ferreira, Artur},
  title     = {GEO Brand Citation Index},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.19450361},
  url       = {https://github.com/arturseo-geo/geo-citation-index}
}
```

---

## Research by The GEO Lab

[thegeolab.net](https://thegeolab.net) — dedicated GEO research platform.
