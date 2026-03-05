# GEO Citation Index — Strategic Review & Improvement Plan

Status: Review
Author: AJ / The GEO Lab
Date: 2026-03-05

---

## The honest assessment

The specs produced so far are technically solid. The gap analysis concept is
genuinely original. The archetype classification is the right research
contribution. The extraction pipeline is well-designed.

But the project as currently specced would take months to build, require
four separate systems to maintain, and produce a database — not content.

AJ's goal is brand authority and published output with minimal effort.
Those two things are almost contradictory to a well-architected data
pipeline. This review resolves that contradiction.

---

## What's strong — keep all of this

- **Gap analysis as the primary insight.** ChatGPT vs Perplexity delta is
  unique data nobody else publishes. This is the research contribution.

- **Archetype classification logic.** The five archetypes (training_dependent,
  retrieval_driven, consensus_dominant, consensus_geo, ghost) are analytically
  coherent. Keep the internal logic exactly as specced.

- **Two-pass brand extraction.** Rule-based first, LLM-assisted fallback.
  Clean architecture, correct design.

- **Temporal query type.** Temporally-framed queries amplify the
  training vs retrieval split most clearly. This is the diagnostic insight
  that makes the panel analytically valuable beyond a simple leaderboard.

- **Deduplication via longest-match-first.** Correct handling of
  "Google Analytics" vs "Google" problem.

- **Test coverage plan.** Keep it. Solid.

---

## The single biggest problem: the pipeline has no content output

The pipeline currently ends at `citation_index` rows in a database.
That is not a publishable output. There is no step that generates the
blog post, social posts, PDF report, or the updated index page on the site.

This means every month AJ would need to:
- Query the database manually
- Interpret the numbers
- Write a blog post from scratch
- Write social posts from scratch
- Update the public page manually

That is not low effort. That is a part-time job.

**The fix:** Add `content_generator.py` as the final pipeline step.
After every run, the pipeline auto-generates:
1. A blog post draft (markdown, ready to paste into WordPress)
2. Five pre-written social posts (LinkedIn + Twitter)
3. A PDF report
4. A JSON file for the public index page

AJ reads, makes minor edits, publishes. 30–45 minutes per month total.
This is the single most important addition to the spec.

---

## Problem 2: Four systems to maintain

Current stack:
- PostgreSQL
- FastAPI backend
- Streamlit admin UI
- Next.js public index

That is four separate things that can break, need updates, and require
deployment. For a one-person operation running monthly batch jobs, this
is enormous overhead.

**What AJ actually needs:**
- Run the pipeline once a month
- Get files out
- Publish them

**Proposed stack:**
- SQLite (single file, zero administration, more than adequate for
  monthly batch jobs with ~75 API calls)
- Single entry point script: `python run_monthly.py`
- No Streamlit UI (the terminal output IS the admin interface)
- No Next.js app (the WordPress page reads a JSON file uploaded monthly)

PostgreSQL and a scheduler are appropriate when many users are hitting a
live API concurrently. A monthly cron job run by one person is not that.
SQLite can always be migrated to PostgreSQL later if the scale demands it.

---

## Problem 3: Eight verticals is too many for authority building

8 verticals × 45 queries × 130 brands = surface-level data on many topics.

The goal is to be the *definitive* source on AI citation data, not a broad
index of many industries. Depth builds authority. Breadth builds noise.

**v1 scope: 3 verticals, 25 queries, 60 brands**

| Vertical | Why v1 |
|----------|--------|
| SEO & Marketing Tools | AJ's existing audience; highest relevance to GEO practitioners |
| CRM & Sales | Most requested by brand managers; strongest archetype contrast |
| AI & LLM Tools | Highest inherent interest; platform bias finding is a research paper on its own |

25 queries produces 75 API calls. Runs in under 30 minutes.
60 brands is enough for meaningful leaderboards.
Each vertical can be covered in more depth.
Expand to additional verticals quarterly — each expansion is a content moment.

---

## Problem 4: The public framing is too technical

"training_dependent", "retrieval_driven", "consensus_geo" — these are correct
internally but create no shareable moment. Brand managers don't know what
retrieval-dependent means. Marketers don't share archetype classifications.

**What creates a shareable moment:**
A specific, named brand, with a specific, alarming finding, explained in
plain language.

"ChatGPT recommends Mailchimp 4× more than Perplexity does. That gap
means Mailchimp exists in AI's memory but is fading from live search."

That is a LinkedIn post. That is what people screenshot and share.

### Public-facing archetype labels

Keep the technical labels in the database for methodology depth.
Display simplified labels on the public index and in social posts.

| Internal label | Public label | What it means in plain language |
|---------------|-------------|--------------------------------|
| `training_dependent` | 🧠 AI Memory Brand | AI was trained on this brand. Live search barely finds it anymore. |
| `ghost` | 🫥 Fading Brand | In AI's memory from years ago. Nearly invisible on live web today. |
| `retrieval_driven` | 🔍 Live Search Brand | Consistently found via live retrieval. GEO may be working. |
| `consensus_dominant` | 👑 Dominant Brand | Strong everywhere. Training AND live retrieval both solid. |
| `consensus_geo` | ⭐ GEO Outlier | Outperforming what its domain authority would predict. |
| `unclassified` | (not shown publicly) | — |

The "AI Memory Brand" and "Fading Brand" labels are alarming to brand
managers in a way that drives shares and inbound traffic. Someone who works
at Mailchimp will share the post that says their brand is fading from live
search. That is the backlink acquisition strategy.

---

## The new content generation pipeline

This is the most important addition. A new module at the end of every run.

### `app/core/content_generator.py`

Runs after `build_citation_index()` completes. Calls the Anthropic API
with the run's output and generates all publishable assets.

**What it produces (saved to `outputs/YYYY-MM/`):**

```
outputs/
└── 2026-03/
    ├── report_2026-03.md          ← Blog post draft
    ├── social_posts_2026-03.txt   ← 5 pre-written posts
    ├── report_2026-03.pdf         ← Formatted PDF report
    └── index_data_2026-03.json    ← For WordPress leaderboard page
```

### Blog post structure (auto-generated, AJ adds commentary)

```markdown
# GEO Brand Citation Index — March 2026
*How AI platforms recommend brands across SEO, CRM, and AI tools*

## What we measured
[AUTO: N brands, N queries, 3 platforms, run date]

## The leaderboard: Top 10 most cited brands this month
[AUTO: ranked table — Brand | ChatGPT | Perplexity | Gemini | Label]

## This month's biggest platform gap
[AUTO: 2-3 paragraphs on the brand with the widest ChatGPT vs Perplexity
delta. Real numbers. Named brand. Plain-language explanation.]

## AI Memory Brand spotlight: [Brand]
[AUTO: named brand, scores, narrative about what the gap means.
This is the shareable section — specific, alarming, concrete.]

## Biggest mover this month: [Brand]
[AUTO: brand that moved most in rank since last run. Positive or negative.]

## Vertical spotlight: [Vertical]  ← rotates monthly
[AUTO: top 5 brands in one vertical with platform breakdown]

## Full data tables
[AUTO: complete ranked tables for all 3 verticals × 3 platforms]

## Methodology
[STATIC: same every month — links to methodology page]
```

AJ's job: read it, add 1-2 paragraphs of personal commentary ("What I
found interesting about this month's data..."), correct any narrative
that seems off, publish. That is all.

### Social posts (auto-generated, 5 per month)

```
POST 1 — LINKEDIN (Report announcement, Day 1)
The GEO Brand Citation Index for [Month] is live.

We tracked [N] brands across ChatGPT, Perplexity, and Gemini.

The headline finding: [SPECIFIC DATA POINT]

Top 5 most cited brands this month:
1. [Brand] — [Label]
2. [Brand] — [Label]
3. [Brand] — [Label]
4. [Brand] — [Label]
5. [Brand] — [Label]

Full report + data tables: [link]
#GEO #AISearch #GenerativeEngineOptimisation

---
POST 2 — TWITTER/X (AI Memory Brand, Day 2)
[Brand] gets recommended by ChatGPT [X]× more often than Perplexity.

That's an AI Memory Brand.

The model was trained on this brand. But live search barely surfaces it.

For brand managers: this gap is a warning signal.

→ GEO Brand Citation Index: [link]

---
POST 3 — LINKEDIN (Platform divergence insight, Day 5)
ChatGPT and Perplexity agreed on very little this month.

The biggest divergence: [specific finding with real numbers]

Why this matters: ChatGPT cites from training data.
Perplexity retrieves from the live web.

When they disagree strongly, you're seeing a brand's AI visibility
deteriorating in real time.

Full breakdown: [link]

---
POST 4 — TWITTER/X (Biggest mover, Day 9)
[Brand] moved [+/-N] places in the GEO Citation Index this month.

[One sentence on why / what changed]

Tracking data from March at: [link]

---
POST 5 — LINKEDIN (Methodology / credibility, Day 14)
How we measure AI citation data — and why platform divergence is
the metric that matters most.

[2-3 sentences from methodology]

GEO Brand Citation Index methodology: [link]
```

### Index JSON (for WordPress leaderboard page)

```json
{
  "run_date": "2026-03-05",
  "report_month": "March 2026",
  "brands": [
    {
      "rank": 1,
      "name": "HubSpot",
      "slug": "hubspot",
      "vertical": "crm-sales",
      "chatgpt_score": 91.2,
      "perplexity_score": 87.4,
      "gemini_score": 89.0,
      "archetype_public": "dominant_brand",
      "archetype_label": "👑 Dominant Brand",
      "delta_rank": 0,
      "trend": "stable"
    },
    ...
  ],
  "meta": {
    "brands_tracked": 60,
    "queries_run": 25,
    "platforms": ["ChatGPT", "Perplexity", "Gemini"],
    "report_url": "https://thegeolab.net/geo-brand-citation-index/march-2026/"
  }
}
```

---

## The WordPress leaderboard page

No Next.js app. A single WordPress page at:
`/geo-brand-citation-index/`

Structure:
- H1: GEO Brand Citation Index
- Intro paragraph (static — explains what the index is)
- "Last updated: [date]" with link to current month's full report
- Interactive leaderboard table (simple JS reading index JSON)
- "Submit your brand" CTA → Google Form (see below)
- FAQ schema block (5 questions, hardcoded — who is this for, how is it
  measured, how often updated, what do the labels mean, how to get included)
- Link to methodology page

The leaderboard table is a simple vanilla JS component. Reads the JSON from
the WordPress media library. Supports filtering by vertical and archetype.
AJ uploads the new JSON file monthly and updates a variable at the top of
the JS block. Two-minute update.

### The brand submission form

Google Form. Three fields:
1. Brand name
2. Website
3. Email (to notify when included)

Results to a Google Sheet. Monthly, AJ checks the sheet, adds qualified
brands to the seed dictionary. 10 minutes per month. Builds the email list.
Drives backlinks when brands tell their followers they're being tracked.

---

## Revised architecture

```
Monthly run: python run_monthly.py
    │
    ├── 1. Query runner (45 min)
    │       ├── ChatGPT: server-side API (gpt-4o-mini)
    │       ├── Gemini:  server-side API (gemini-1.5-flash)
    │       └── Perplexity: browser component (Puter.js)
    │           └── [browser tab must stay open]
    │
    ├── 2. Brand extractor
    │       ├── Pass 1: rule-based (brand_dictionary)
    │       └── Pass 2: LLM-assisted (if < 3 brands found)
    │
    ├── 3. Citation scorer
    │       ├── Position-weighted scores per brand × platform
    │       ├── Normalise within vertical × platform × run
    │       ├── Compute cross-platform deltas
    │       └── Classify archetypes
    │
    ├── 4. Index builder
    │       ├── Materialise citation_index rows
    │       └── Update brand.platform_citation_summary
    │
    └── 5. Content generator (NEW — the unlock)
            ├── Call Anthropic API with run data
            ├── Generate blog post draft (markdown)
            ├── Generate 5 social posts
            ├── Generate PDF report
            └── Generate index JSON

    Output: outputs/2026-03/
    ├── report_2026-03.md
    ├── social_posts_2026-03.txt
    ├── report_2026-03.pdf
    └── index_data_2026-03.json
```

Infrastructure:
- SQLite (single file — `citation_index.db`)
- No FastAPI backend needed
- No Streamlit UI needed
- No Next.js app
- No scheduler — just `python run_monthly.py`

---

## AJ's monthly routine (what 30 min/month looks like)

**Day 1 of each month:**

1. Open terminal (5 min)
   ```
   python run_monthly.py
   ```
   Leave it running. It takes ~30 min for the query phase.
   Keep the browser tab open for Perplexity.

2. Review output files (15 min)
   - Read `report_[month].md` — check the auto-generated narrative
   - Add 1-2 paragraphs of personal commentary
   - Skim `social_posts_[month].txt` — adjust tone if needed
   - Check the PDF looks clean

3. Publish (10 min)
   - Upload `index_data_[month].json` to WordPress media library
   - Update the JS variable on the leaderboard page
   - Paste blog post into WordPress → publish
   - Upload PDF as downloadable resource

4. Schedule social posts (5 min)
   - Paste into Buffer/Later for the next 2 weeks
   - Done

Total active time: ~30 min.
The query run itself is passive — it runs while you do other things.

---

## What to add to the specs

### DB models — minimal changes

- Change PostgreSQL to SQLite as default (comment says "migrate to PG if scale requires")
- Add `archetype_label_public` to `Brand` and `CitationIndex` — the consumer-friendly label
  derived from `citation_archetype` at write time
- Add `report_generated` boolean to `QueryRun` — tracks whether content generation completed

### Query panel — changes from v2

- Narrow to 3 verticals for v1 (SEO/Marketing, CRM/Sales, AI Tools)
- Reduce to 25 queries total (from 45)
- Keep all 5 intent types including temporal
- Document vertical expansion as a quarterly roadmap milestone (each expansion = content moment)

### New modules to add

**`app/core/content_generator.py`**

Primary inputs: `QueryRun` + all associated `CitationIndex` rows + previous run's
`CitationIndex` rows for delta narrative.

Key functions:
```python
def generate_monthly_report(run: QueryRun, db: Session) -> ReportBundle
def build_prompt_context(run: QueryRun, db: Session) -> dict
def generate_blog_post(context: dict) -> str
def generate_social_posts(context: dict) -> list[str]
def generate_index_json(run: QueryRun, db: Session) -> dict
```

The blog post generation prompt must:
- Instruct Claude to be specific (real brand names, real numbers, not hedged)
- Instruct Claude to write in AJ's voice (first-person, research-oriented,
  "I measured", "the data shows")
- Include the full ranking table and delta data in the prompt context
- Flag the top archetype finding explicitly so Claude leads with it
- Output valid markdown that pastes directly into WordPress

The social post generation prompt must:
- Generate exactly 5 posts in the formats specified above
- Use the single most surprising finding as the hook for Post 2
- Not include hashtags that aren't already established in the calendar
- Match the voice from the social calendar already drafted

**`run_monthly.py`** — single entry point

```python
# Usage:
# python run_monthly.py           → full run
# python run_monthly.py --dry-run → validate config without running queries
# python run_monthly.py --content-only → regenerate content from last run's data

def main():
    run = create_query_run()
    execute_queries(run)           # step 1
    extract_brands(run)            # step 2
    compute_scores(run)            # step 3
    build_index(run)               # step 4
    generate_content(run)          # step 5
    print_summary(run)             # terminal output
```

**`scripts/seed_dictionary.py`** — unchanged from original plan

**`app/services/report_writer.py`** — PDF generation

Reuses GEO-OS `pdf_generator.py` pattern. ReportLab.
Sections: cover page → summary table → platform divergence chart →
spotlight brands → full data tables → methodology.

---

## Expansion roadmap (low effort, each step = content moment)

| Milestone | What it adds | Content opportunity |
|-----------|-------------|---------------------|
| v1 Launch | 3 verticals, 60 brands | "Introducing the GEO Brand Citation Index" |
| v1.1 — Q2 | Add verticals 4-5 (Project Mgmt + Email) | "We expanded the index to cover 5 verticals" |
| v1.2 — Q3 | Add vertical 6-7 (Analytics + Cloud) | "The index now covers 7 software categories" |
| v2 — Q4 | Add cities index (most cited cities in travel/hospitality AI answers) | "We launched a Cities Citation Index" |
| v2.1 | Add publications index (most cited news sources) | "We now track which publications AI trusts most" |
| v3 | Add "submit your brand" results to annual report | "The GEO Brand Citation Report — Annual 2026" |

Each expansion requires: add vertical to query panel, add brands to dictionary,
rerun, get new content automatically. 30 min of actual work.

---

## The compound effect

Month 1: Publish the index. One report. 5 social posts. Low traffic.

Month 3: The "AI Memory Brand" label has started appearing in SEO blogs.
Brand managers are sharing it. The Mailchimp finding (or whoever fits the
archetype) gets shared by someone with an audience.

Month 6: thegeolab.net has 6 months of citation trend data. Nobody else has
this. Journalists ask for comment. Agencies reference the index in their
proposals. The index page is one of the top-ranking results for "AI citation
data" and "GEO research".

Month 12: The annual report becomes a standalone PR moment. "12 months of
AI citation data — here's what changed." This is the piece that gets picked
up. This is when thegeolab.net becomes a reference rather than a blog.

The key is consistency. One run per month. Content comes out automatically.
No month is skipped because there's nothing to write.

---

## Priority build order

1. `scripts/seed_dictionary.py` — needed before anything runs
2. `app/models/db.py` — finalise with SQLite default + public label fields
3. `app/core/brand_extractor.py` — rule-based pass only for v1
4. `app/core/citation_scorer.py` — scoring + deltas + archetype
5. `app/core/index_builder.py` — materialise citation_index
6. `app/core/content_generator.py` — THE UNLOCK (do not ship without this)
7. `app/services/report_writer.py` — PDF generation
8. `run_monthly.py` — single entry point wiring everything together
9. WordPress leaderboard page — HTML/JS, simple
10. Brand submission form — Google Form, 10 min

The query runner already exists in GEO-OS as the Query Tracker.
Copy and adapt — do not rebuild from scratch.
