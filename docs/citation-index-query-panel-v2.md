# GEO Citation Index — Query Panel Design v1
# Version: 0.2 (revised to incorporate gap analysis and temporal intent type)

Status: Draft
Author: AJ / The GEO Lab
Last updated: 2026-03-05

Changelog from v0.1:
  - Added `temporal` intent type (5 queries — one per key vertical)
  - Total panel: 45 queries (up from 40)
  - Added gap analysis role column to intent type definitions
  - Added platform consistency constraint (hard rule — all 3 platforms required)
  - Added archetype prediction notes per vertical
  - Added temporal query diagnostic rationale
  - Expanded governance rules to cover threshold versioning

---

## Design Principles

**Gap analysis is the primary output — not rankings.**
Every query exists to generate comparable data across ChatGPT (model_memory),
Perplexity (live_retrieval), and Gemini (hybrid). The delta between platforms
is the finding. A single-platform query has no analytical value for this index.

**Reproducibility over breadth.**
Queries must produce structurally similar responses on every run. Avoid
queries that are inherently news-dependent or produce different response
formats across runs.

**Query diversity within vertical.**
Five intent types capture different citation contexts and different
gap analysis signals. Temporal queries specifically amplify the
training vs retrieval split.

**No brand names in queries — except comparison and temporal.**
Comparison queries require named brands by definition.
Temporal queries may name a year but not a brand.

**All three platforms on every run — non-negotiable.**
`query_panels.requires_all_platforms = True` enforces this at DB level.
If any platform fails mid-run, the run is marked `gap_analysis_valid = False`
and archetype classification is skipped for that run.

---

## Intent Type Definitions

| intent_type | Query pattern | Gap analysis role |
|-------------|--------------|------------------|
| `recommendation` | "What are the best [category] tools?" | Baseline citation signal across all platforms |
| `best_for` | "What is the best [category] for [use case]?" | Niche authority — often more divergent than general recommendation |
| `comparison` | "Compare [Brand A] vs [Brand B]" | Head-to-head — which platform favours which brand |
| `category_open` | "Which [category] platforms are most popular?" | Unprompted association — reveals model memory most clearly |
| `temporal` | "What are the best [category] tools in [year]?" | Training cutoff diagnostic — strongest signal for retrieval_driven vs training_dependent split |

### Why temporal queries matter for gap analysis

A training-dependent brand will appear consistently in both standard
recommendation queries and temporal queries — model memory ignores
the year framing.

A retrieval-driven brand (newer, strong live web signals, limited training
data) will appear on Perplexity for temporal queries but be absent or
lower-ranked on ChatGPT. This is the clearest available signal that
the brand's citations come from live retrieval, not model memory.

A brand appearing on ChatGPT for standard queries but absent from ChatGPT
temporal queries is a possible ghost candidate — model memory is fading.

---

## v1 Panel: 45 Queries × 8 Verticals

Total: 45 queries (40 standard + 5 temporal, one per key vertical)
Platforms: ChatGPT, Perplexity, Gemini
Total runs per execution: 135 (45 × 3)

---

### Vertical 1: SEO & Marketing Tools
`vertical_slug: seo-marketing`

| # | query_text | intent_type | gap_analysis_note |
|---|-----------|-------------|------------------|
| 1 | What are the best SEO tools available right now? | recommendation | Baseline |
| 2 | What are the best tools for keyword research? | recommendation | Baseline |
| 3 | What is the best SEO tool for a small business? | best_for | Niche signal |
| 4 | What is the best SEO tool for enterprise teams? | best_for | Niche signal |
| 5 | Which SEO platforms are most widely used by professionals? | category_open | Model memory signal |
| T1 | What are the best SEO tools in 2026? | temporal | Training cutoff diagnostic |

**Archetype predictions:**
- Ahrefs, Semrush: likely `consensus_dominant` — years of training data + strong backlink profile
- Surfer SEO, Clearscope: watch for `retrieval_driven` — newer tools, strong content marketing
- Moz: watch for `training_dependent` — historically strong, possible live retrieval decline

---

### Vertical 2: CRM & Sales
`vertical_slug: crm-sales`

| # | query_text | intent_type | gap_analysis_note |
|---|-----------|-------------|------------------|
| 7 | What are the best CRM tools available right now? | recommendation | Baseline |
| 8 | What CRM do most sales teams use? | category_open | Model memory signal |
| 9 | What is the best CRM for a small business? | best_for | Niche signal |
| 10 | What is the best CRM for enterprise sales teams? | best_for | Niche signal |
| 11 | Compare Salesforce vs HubSpot — which is better? | comparison | Head-to-head divergence |
| T2 | What are the best CRM tools in 2026? | temporal | Training cutoff diagnostic |

**Archetype predictions:**
- Salesforce: likely `consensus_dominant` or `training_dependent` — category default in model memory
- HubSpot: likely `consensus_dominant` — strong training data AND live retrieval
- Close CRM, Attio: watch for `retrieval_driven` — newer entrants with strong content
- SugarCRM: watch for `ghost` — historically cited, possible live retrieval decline

---

### Vertical 3: Project Management
`vertical_slug: project-management`

| # | query_text | intent_type | gap_analysis_note |
|---|-----------|-------------|------------------|
| 13 | What are the best project management tools? | recommendation | Baseline |
| 14 | What project management software do most teams use? | category_open | Model memory signal |
| 15 | What is the best project management tool for remote teams? | best_for | Niche signal |
| 16 | What is the best free project management tool? | best_for | Niche signal |
| 17 | Compare Asana vs Monday.com — which is better for teams? | comparison | Head-to-head divergence |

---

### Vertical 4: AI & LLM Tools
`vertical_slug: ai-llm-tools`

| # | query_text | intent_type | gap_analysis_note |
|---|-----------|-------------|------------------|
| 18 | What are the best AI writing tools available right now? | recommendation | Baseline |
| 19 | What are the most popular AI tools for businesses? | category_open | Model memory signal |
| 20 | What is the best AI tool for content creation? | best_for | Niche signal |
| 21 | What is the best AI coding assistant? | best_for | Niche signal |
| 22 | Compare ChatGPT vs Claude — which is better for writing? | comparison | Known platform bias — see note |
| T3 | What are the most useful AI tools in 2026? | temporal | Training cutoff diagnostic |

**Known methodology bias — AI Tools comparison:**
ChatGPT and Gemini are being asked to evaluate their own competitors.
Their responses will structurally differ from Perplexity's.
- ChatGPT is unlikely to strongly recommend Claude over itself
- Gemini is unlikely to strongly recommend ChatGPT over itself
- Perplexity has no stake in the outcome

This query is retained because the *divergence itself* is a finding worth
publishing. Flag in methodology documentation. Do not use this query's
data to compute archetype classification — exclude from archetype scoring,
include in raw citation data with bias_flag = True.

Consider adding a bias_flag field to panel_queries in v1.1.

---

### Vertical 5: Cloud & Infrastructure
`vertical_slug: cloud-infrastructure`

| # | query_text | intent_type | gap_analysis_note |
|---|-----------|-------------|------------------|
| 23 | What are the best cloud hosting platforms? | recommendation | Baseline |
| 24 | Which cloud providers do most companies use? | category_open | Model memory signal |
| 25 | What is the best cloud platform for startups? | best_for | Niche signal |
| 26 | What is the best cloud platform for enterprise workloads? | best_for | Niche signal |
| 27 | Compare AWS vs Google Cloud — which is better? | comparison | Head-to-head divergence |
| T4 | What are the best cloud hosting options in 2026? | temporal | Training cutoff diagnostic |

**Archetype predictions:**
- AWS, Google Cloud, Azure: likely `consensus_dominant` — category giants
- DigitalOcean, Hetzner: watch for `retrieval_driven` — strong developer community content
- Heroku: strong `ghost` candidate — historically cited, significantly declined post-Salesforce acquisition

---

### Vertical 6: Email Marketing
`vertical_slug: email-marketing`

| # | query_text | intent_type | gap_analysis_note |
|---|-----------|-------------|------------------|
| 28 | What are the best email marketing platforms? | recommendation | Baseline |
| 29 | What email marketing tools do most small businesses use? | best_for | Niche signal |
| 30 | What is the best email marketing tool for ecommerce? | best_for | Niche signal |
| 31 | Which email marketing platforms are most popular? | category_open | Model memory signal |
| 32 | Compare Mailchimp vs Klaviyo — which is better? | comparison | Head-to-head divergence |

**Archetype predictions:**
- Mailchimp: watch for `training_dependent` — historically dominant, losing ground to Klaviyo in live recommendations
- Klaviyo: watch for `retrieval_driven` — aggressive content marketing, strong ecommerce positioning
- Brevo (formerly Sendinblue): interesting test — brand rename mid-training-period may create split

---

### Vertical 7: Analytics & BI
`vertical_slug: analytics`

| # | query_text | intent_type | gap_analysis_note |
|---|-----------|-------------|------------------|
| 33 | What are the best analytics tools for websites? | recommendation | Baseline |
| 34 | What is the best analytics platform for small businesses? | best_for | Niche signal |
| 35 | What analytics tools do enterprise teams use most? | best_for | Niche signal |
| 36 | Which web analytics platforms are most widely used? | category_open | Model memory signal |
| 37 | Compare Google Analytics vs Mixpanel — which is better? | comparison | Head-to-head divergence |
| T5 | What are the best web analytics tools in 2026? | temporal | Training cutoff diagnostic |

**Archetype predictions:**
- Google Analytics: likely `consensus_dominant` or `training_dependent`
- Plausible, Fathom, PostHog: strong `retrieval_driven` candidates — privacy-first narrative
  well-represented in recent developer content
- Adobe Analytics: watch for `training_dependent` — enterprise tool, limited recent web content

---

### Vertical 8: HR & Recruiting
`vertical_slug: hr-recruiting`

| # | query_text | intent_type | gap_analysis_note |
|---|-----------|-------------|------------------|
| 38 | What are the best HR software platforms? | recommendation | Baseline |
| 39 | What are the best tools for recruiting and hiring? | recommendation | Baseline |
| 40 | What is the best HR platform for small businesses? | best_for | Niche signal |
| 41 | Which HR and recruiting platforms are most widely used? | category_open | Model memory signal |
| 42 | Compare Greenhouse vs Lever — which is better for recruiting? | comparison | Head-to-head divergence |

---

## Query Distribution Summary

| intent_type | Count | % | Gap analysis role |
|------------|-------|---|------------------|
| recommendation | 13 | 28.9% | Baseline citation signal |
| best_for | 16 | 35.6% | Niche authority signal |
| comparison | 8 | 17.8% | Head-to-head divergence |
| category_open | 8 | 17.8% | Model memory signal |
| temporal | 5 | 11.1% | Training cutoff diagnostic |
| **Total** | **45** | | |

Note: temporal queries overlap with other verticals — they are additive,
not replacing existing queries.

---

## Comparison Pairs

| Vertical | Pair | Expected finding |
|---------|------|-----------------|
| CRM | Salesforce vs HubSpot | ChatGPT likely favours Salesforce (training dominance); Perplexity may balance |
| Project Management | Asana vs Monday.com | Watch for Monday.com retrieval_driven signal — heavy paid content marketing |
| AI Tools | ChatGPT vs Claude | Platform bias — excluded from archetype scoring |
| Cloud | AWS vs Google Cloud | Both likely consensus_dominant |
| Email | Mailchimp vs Klaviyo | Classic training_dependent vs retrieval_driven test case |
| Analytics | Google Analytics vs Mixpanel | Google Analytics training_dependent; Mixpanel retrieval_driven candidate |
| HR | Greenhouse vs Lever | Both mid-tier — interesting ghost risk given Lever's ownership changes |

---

## Seed Brand Dictionary

~130 brands across 8 verticals. Pre-loaded before first run.

### SEO & Marketing
Ahrefs, Semrush, Moz, Google Search Console, Screaming Frog, Surfer SEO,
Clearscope, MarketMuse, SE Ranking, Mangools, Ubersuggest, Majestic,
Serpstat, BrightEdge, Conductor, Botify, DeepCrawl, SpyFu, Similarweb

### CRM & Sales
Salesforce, HubSpot, Zoho CRM, Pipedrive, Microsoft Dynamics,
Monday CRM, Freshsales, Close CRM, Copper, Insightly, Attio,
Zendesk Sell, Capsule, Nimble, Keap, ActiveCampaign, Nutshell

### Project Management
Asana, Monday.com, Jira, Trello, Notion, ClickUp, Linear, Basecamp,
Smartsheet, Wrike, Teamwork, Airtable, Height, Todoist, Microsoft Project

### AI & LLM Tools
ChatGPT, Claude, Gemini, Copilot, Perplexity, Jasper, Copy.ai,
Writesonic, Midjourney, DALL-E, Stable Diffusion, GitHub Copilot,
Cursor, Replit, Windsurf, Grammarly, Notion AI, Otter.ai

### Cloud & Infrastructure
AWS, Google Cloud, Microsoft Azure, DigitalOcean, Cloudflare,
Vercel, Netlify, Heroku, Fly.io, Railway, Render, Hetzner,
Linode, IBM Cloud, Oracle Cloud

### Email Marketing
Mailchimp, Klaviyo, Constant Contact, ActiveCampaign, Campaign Monitor,
Brevo, Sendinblue, ConvertKit, Drip, GetResponse, Omnisend,
MailerLite, Moosend, AWeber, Sendgrid, Postmark

Note: Brevo and Sendinblue are aliases of the same brand —
add both to brand_dictionary pointing to the same brand_id.
First run will be diagnostic for the rename split.

### Analytics & BI
Google Analytics, Mixpanel, Amplitude, Heap, Hotjar, Pendo,
Fullstory, Segment, Matomo, Plausible, Fathom, PostHog,
Looker, Tableau, Power BI, Metabase, Grafana, Adobe Analytics

### HR & Recruiting
Greenhouse, Lever, Workday, BambooHR, Rippling, Gusto,
ADP, Paychex, Personio, Bob, HiBob, Namely, UKG,
Jobvite, iCIMS, SmartRecruiters, Workable, Breezy HR

Note: Bob and HiBob are aliases of the same brand (HiBob).

---

## Gap Analysis Interpretation Guide

Published in methodology page. Also guides QA review of first run output.

### Reading the deltas

| perplexity_vs_chatgpt_delta | Interpretation |
|-----------------------------|---------------|
| > +20 | Strong retrieval_driven signal |
| +10 to +20 | Moderate retrieval advantage |
| -10 to +10 | Consistent across platforms (consensus candidate) |
| -10 to -20 | Moderate training advantage |
| < -20 | Strong training_dependent signal |

### Ghost brand detection

A brand qualifies as ghost candidate when:
- chatgpt_normalised >= 35 (present in model memory)
- perplexity_normalised <= 15 (nearly absent from live retrieval)
- The gap has persisted for 2+ consecutive runs (single-run ghost is inconclusive)

Require 2-run confirmation before publishing ghost classification publicly.
Single-run ghost candidates are flagged internally as `possible_ghost`.

### consensus_geo detection

Most difficult classification — requires external backlink signal.
v1 process:
1. Flag brands meeting score thresholds as `possible_consensus_geo`
2. Manual review: check Ahrefs/Semrush DR for flagged brands
3. Brands with DR < 40 and consistent cross-platform scores confirmed
   as `consensus_geo`
4. Document manual review step in methodology

---

## Query Panel Governance Rules

**Adding queries:**
- Version bump required (v1.0 → v1.1)
- Temporal queries: update year in query text annually — this IS permitted
  without version bump (year update is expected maintenance)
- Never modify non-temporal query text — deprecate and add new

**Removing queries:**
- `is_active = False` only — never delete
- Historical runs remain attributable to original query text

**Comparison pair updates:**
- Reviewed quarterly
- Swap pairs when brands become non-comparable (acquisition, discontinuation)
- Document pair changes in panel notes

**Threshold versioning:**
- Any change to `ARCHETYPE_THRESHOLDS` in config.py requires
  `ARCHETYPE_THRESHOLD_VERSION` bump
- New version stored on subsequent `query_runs` and `archetype_snapshots`
- Historical snapshots remain attributed to their threshold version
- Do not retroactively reclassify historical snapshots under new thresholds

**Platform consistency:**
- `requires_all_platforms = True` on all panels
- If a platform run fails, mark `gap_analysis_valid = False` on the run
- Do not publish archetype classifications from invalid runs
- Retry failed platform runs before triggering index rebuild

---

## v2 Expansion Candidates

**Additional temporal queries per vertical:**
One temporal query per vertical in v1. Expand to 2-3 per vertical in v2
to increase diagnostic signal for temporal split analysis.

**Negative/problem framing:**
- "What are the best alternatives to [Brand]?"
- Captures displacement brands — who AI recommends when users are leaving

**Role-specific queries:**
- "What tools do content marketers use for keyword research?"
- Captures role-based authority — different brand tier from general recommendation

**Additional verticals (v2):**
- Design tools (Figma, Canva, Sketch)
- Customer support / helpdesk
- Finance & accounting
- Security & compliance
- Developer tools / API platforms
