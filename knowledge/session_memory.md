# GEO Citation Index - Session Memory

Last Updated: 2026-03-07

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

## Monthly Process (20 min/month)

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
| `PERPLEXITY_API_KEY` | Perplexity queries (live web) |
| `ANTHROPIC_API_KEY` | Content generation (Claude) |

All 3 platforms now run via API (no browser needed).

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

### 2026-03-05 — Local Environment Ready
- Created Python venv with all dependencies installed
- Configured `.env` with API keys (OpenAI, Gemini, Anthropic)
- Seeded database: 3 platforms, 3 verticals, 38 brands, 18 queries
- Dry-run test **PASSED** — system ready for first monthly run

### 2026-03-05 — Full API Mode Enabled
- Added new OpenAI API key with credits
- Added Perplexity API key (live web retrieval)
- Updated pipeline to run all 3 platforms via API (no browser needed)
- All queries now run server-side: ChatGPT + Gemini + Perplexity

### 2026-03-05 — First Successful Run!
- **Run ID:** 494f9bf0-17ed-4f23-8bbc-13e70dcd4bb8
- **Queries:** 54 total (18 × 3 platforms)
- **Brands found:** 392 mentions | 62 new brands discovered
- **Gap analysis:** Valid (cross-platform deltas computed)
- **Output files:**
  - `outputs/2026-03/report_2026-03.md` (blog post)
  - `outputs/2026-03/social_posts_2026-03.txt` (5 social posts)
  - `outputs/2026-03/index_data_2026-03.json` (leaderboard data)
  - `outputs/2026-03/report_2026-03.pdf` (PDF report)

### 2026-03-05 — Content Regenerated with Real Data
- Blog post rewritten with actual brand names, rankings, and deltas
- 5 social posts created with real numbers from the JSON data
- **Key findings documented:**
  - Dominant Brands: ChatGPT (100%), Salesforce (100%), HubSpot (71-80%), Semrush (90-100%)
  - Live Search Brand: Claude (+50 delta — biggest positive gap)
  - Fading Brand: Moz (-44 delta — ChatGPT remembers, Perplexity doesn't)
  - AI Memory Brand: Ahrefs (-48 delta), Google Search Console (-29 delta)
  - GEO Outliers: Copilot, Zoho CRM (consistent across all platforms)

---

## VPS Access

**Always use Tailscale IP for SSH:**
```bash
ssh root@100.87.191.9
```
- Password: `Digital@080700`
- WordPress path: `/var/www/thegeolab/`
- Theme path: `/var/www/thegeolab/wp-content/themes/geolab-theme/`

---

### 2026-03-06 — Design System Updated (Editorial Style)

Updated thegeolab.net to new editorial design system matching the Citation Index pages:

| Element | Before | After |
|---------|--------|-------|
| Background | White #FFFFFF | Warm beige #f8f5f0 |
| Body font | System UI | DM Sans |
| Heading font | Montserrat | DM Serif Display |
| Mono font | — | DM Mono |
| Accent/links | Blue #2E75B6 | Amber #8b6914 |
| H2 color | Dark | Blue #2E75B6 |

**Files modified on VPS:**
- `/var/www/thegeolab/wp-content/themes/geolab-theme/theme.json`
- `/var/www/thegeolab/wp-content/themes/geolab-theme/functions.php` (Google Fonts)

**Backups:**
- `theme.json.backup-blue-20260306`
- `functions.php.backup-20260306`

---

### 2026-03-06 — Pages Ready for Publishing

**New pages to publish (in Downloads folder):**

| Page | File | Slug | Schedule |
|------|------|------|----------|
| Citation Index | `geo-citation-index-page.html` | `/geo-brand-citation-index/` | Sat Mar 8 |
| Methodology | `geo-methodology-page.html` | `/geo-brand-citation-index/methodology/` | Sun Mar 9, 9:00 |
| Explainer (Evergreen) | `geo-evergreen-page.html` | `/geo-brand-citation-index/explainer/` | Sun Mar 9, 13:00 |
| Blog Post | `geo-blog-post-march-2026.html` | `/2026/03/moz-scores-3-7-perplexity-march-2026-geo-brand-citation-index/` | Mon Mar 10, 9:00 |

---

### 2026-03-06 — Rank Math SEO Optimization

**PageSpeed Case Study Optimization (Post 221):**
- Original score: 24/100
- Final score: 74/100 (+50 points)
- Key insight: Choose keywords that match existing content, don't force content to match keywords

**Optimization Steps:**
1. Changed focus keyword from "PageSpeed WordPress mobile" to "pagespeed optimization, wordpress performance, quad 100 score" (+38 points)
2. Added intro paragraph with keywords (+8 points)
3. Modified H2 headings to include keywords
4. Added Table of Contents (+2 points)
5. Updated image alt text with keywords (+2 points)

**Rank Math Findings:**

| Issue | Solution |
|-------|----------|
| Schema shows "Off" | Do NOT set `rank_math_rich_snippet` explicitly — let Rank Math use global defaults |
| SEO Score shows "N/A" | Scores only calculate client-side when post opened in editor |
| TOC block causes JS error | Rank Math TOC blocks added via WP-CLI are malformed — use simple HTML `<div class="toc-box">` instead |
| Inline JSON-LD causes PHP error | Remove inline `<script type="application/ld+json">` from post content — let Rank Math generate schema |
| First paragraph has no keywords | Move keyword-rich intro BEFORE metadata lines — first `<p>` tag must contain focus keywords |

**New Blog Post Created:**
- **ID:** 392
- **Title:** From 24 to 74: A Rank Math SEO Score Optimization Case Study
- **Slug:** `/rank-math-seo-optimization-case-study/`
- **Scheduled:** Monday, March 13, 2026 at 9:00

**Pages with TOC Added:**
- Page 7 (GEO Stack)
- Page 22 (Extractability)
- Page 23 (Retrieval Probability)
- Page 6 (What Is GEO)
- Page 57 (Experiment 001)
- Page 221 (PageSpeed case study)
- Page 392 (Rank Math case study)

**All Pages/Posts Configured:**
- Focus keywords set for all 26 pages/posts
- SEO titles and descriptions configured
- Schema uses global defaults (Article for pages, BlogPosting for posts)

---

### 2026-03-06 — Log Page & Ebooks Page Layout Updates

**Log Page (`/log/`) - Two-Column Post Layout:**
- Template: `templates/page-log.html`
- Layout: Featured image (160px) on left, title + excerpt on right (no date shown)
- **REQUIREMENTS for all posts:**
  1. MUST have a featured image set for proper display
  2. MUST have a custom excerpt set (avoid auto-generated excerpt showing metadata)
- Posts without featured images will show empty space on left
- Posts without custom excerpts will show metadata lines from post content

**Ebooks Page (`/ebooks/`) - Two-Column Layout:**
- Thumbnail (140px) on left, title/description/link on right
- All 6 ebooks have thumbnails from uploaded images (IDs 428-433)

**Featured Images for All Posts:**
| Post ID | Title | Image ID |
|---------|-------|----------|
| 57 | Experiment 001 | 257 |
| 221 | PageSpeed Case Study | 227 |
| 58 | 100% Citation Rate | 256 |
| 385 | Moz Scores 3.7 | 415 |
| 392 | Rank Math Case Study | 419 |

---

### 2026-03-06 — Citation Index Page JavaScript Fix

**Page 382 (GEO Brand Citation Index) — Platform Filter Buttons Fixed:**

**Bug:** Clicking ChatGPT/Perplexity/Gemini buttons didn't change the table display.

**Cause:** The `setPlatform()` function in `page-geo-brand-citation-index.php` only updated button styling but never:
1. Changed the sort dropdown to match the selected platform
2. Called `renderTable()` to re-render the table

**Fix Applied:**
```javascript
function setPlatform(plat, btn) {
  const sel = document.getElementById('sortSelect');
  if (plat === 'delta') sel.value = 'delta-desc';
  else if (plat === 'chatgpt') sel.value = 'chatgpt-desc';
  else if (plat === 'perplexity') sel.value = 'perplexity-desc';
  else if (plat === 'gemini') sel.value = 'gemini-desc';
  activePlatform = plat;
  document.querySelectorAll('.plat-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  renderTable();  // Added this line
}
```

**File Modified:** `/var/www/thegeolab/wp-content/themes/geolab-theme/page-geo-brand-citation-index.php`

---

### 2026-03-06 — Knowledge Folder & Sync Standardization

**All 4 repos now have standardized knowledge/ folder:**

| Repo | Location | Contents |
|------|----------|----------|
| geo-citation-index | PC only | PROJECT_CONTEXT.md, session_memory.md, failure_registry.yml |
| GEO_OS | PC only | PROJECT_CONTEXT.md, session_memory.md, failure_registry.yml |
| geo-lab-social | PC + VPS | PROJECT_CONTEXT.md, session_memory.md, failure_registry.yml |
| thegeolab-core | VPS only | PROJECT_CONTEXT.md, session_memory.md, failure_registry.yml |

**Sync completed across:**
- Local PC (Windows)
- VPS (100.87.191.9)
- GitHub (all 4 repos)

**Updated documentation:**
- README.md files updated with Perplexity API info
- PROJECT_CONTEXT.md added to all repos
- failure_registry.yml added to all repos

---

### 2026-03-07 — GitHub Actions Docs Integrity Fix

**Problem:** Docs Integrity workflow failing because `scripts/check_docs_integrity.py` required `app/backend/main.py` which doesn't exist (project has no FastAPI API layer yet).

**Fix Applied to `scripts/check_docs_integrity.py`:**
1. Made `app/backend/main.py` optional — logs note and continues with empty route set
2. Added HTML comment block skipping in `parse_endpoint_index()` — placeholder routes in `<!-- -->` comments were being parsed

**Result:** Workflow now passes with output:
```
Note: app/backend/main.py not found (no API layer yet)
[Endpoint coverage] OK
[Model coverage] OK
Docs integrity check passed.
```

**Added:** FAIL-012 to failure_registry.yml documenting this fix.

### 2026-03-07 — Git Push Solution

**Problem:** SSH keys have permission issues on both WSL and Windows CMD (`Load key ... Permission denied`).

**Solution:** Use HTTPS remote from Windows CMD (not WSL):
```cmd
git remote set-url origin https://github.com/arturseo-geo/geo-citation-index.git
git push
```

**Why HTTPS works from Windows:**
- Windows has Git Credential Manager that handles GitHub authentication
- WSL doesn't have access to Windows credential store
- SSH keys have file permission issues on Windows

**Current remote configuration:**

| Repo | Location | Remote Type | Push From |
|------|----------|-------------|-----------|
| geo-citation-index | PC | HTTPS | Windows CMD |
| GEO_OS | PC | SSH | Switch to HTTPS |
| geo-lab-social | PC + VPS | SSH | VPS |
| thegeolab-core | VPS | SSH | VPS |

**VPS Git Config:**
```bash
git config --global user.email "jorge@thegeolab.net"
git config --global user.name "The GEO Lab"
```

---
