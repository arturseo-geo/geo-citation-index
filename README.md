# GEO Brand Citation Index

Monthly tracker measuring which brands ChatGPT, Perplexity, and Gemini recommend — and why the gap between platforms tells you more than any single ranking.

Published at [thegeolab.net/geo-brand-citation-index](https://thegeolab.net/geo-brand-citation-index/)

---

## What this is

Every month this system runs 25 questions across three AI platforms (ChatGPT, Perplexity, Gemini), extracts every brand mentioned in the responses, scores each brand by citation prominence, and computes the delta between platforms.

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

Keep the browser tab open when prompted — Perplexity queries run in the browser via Puter.js.

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
│   └── perplexity_runner.html  ← Browser-side Perplexity via Puter.js
├── scripts/
│   ├── seed_dictionary.py      ← One-time brand dictionary seed
│   ├── check_docs_integrity.py ← CI: model coverage check
│   └── auto_push.ps1           ← Windows auto-commit helper
├── knowledge/
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
GEMINI_MODEL=gemini-1.5-flash
ANTHROPIC_API_KEY=sk-ant-...
```

Perplexity runs via [Puter.js](https://puter.com/) in the browser — no API key required.

---

## Monthly routine

1. `python run_monthly.py` — leave running (~40 min, mostly passive)
2. Keep the browser tab open when Perplexity queries execute
3. Review `outputs/YYYY-MM/report_YYYY-MM.md` — add one paragraph of commentary
4. Skim `outputs/YYYY-MM/social_posts_YYYY-MM.txt` — adjust tone if needed
5. Upload `outputs/YYYY-MM/index_data_YYYY-MM.json` to WordPress
6. Publish the report, schedule social posts

Total active time: ~30 minutes.

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
- 25 queries, 60 brands
- 3 platforms: ChatGPT, Perplexity, Gemini

Vertical expansion is planned quarterly — each expansion is a content moment.

---

## Docs

- [DB Models](docs/citation-index-db-models-v2.md)
- [Query Panel Design](docs/citation-index-query-panel-v2.md)
- [Brand Extractor & Scorer Spec](docs/citation-index-extractor-scorer-spec.md)
- [Strategic Review](docs/citation-index-strategic-review.md)

---

## Research by The GEO Lab

[thegeolab.net](https://thegeolab.net) — dedicated GEO research platform.
