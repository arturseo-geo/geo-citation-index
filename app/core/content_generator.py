"""
Content Generator — auto-generates all monthly publication assets
from completed run data via the Anthropic API.

Produces (in outputs/YYYY-MM/):
  report_YYYY-MM.md        — Blog post draft, ready to paste into WordPress
  social_posts_YYYY-MM.txt — 5 pre-written posts (LinkedIn + Twitter)
  report_brief_YYYY-MM.txt — Internal brief used as generation context

This is the module that makes the index sustainable as a solo operation.
Without it, the pipeline produces data that requires manual writing every month.
With it, the monthly routine is 30 minutes: run script, review output, publish.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import anthropic

from app.core.config import ANTHROPIC_API_KEY, OUTPUTS_DIR, ARCHETYPE_PUBLIC_LABELS
from app.models.db import CitationIndex, ArchetypeSnapshot, QueryRun, Brand
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

GENERATION_MODEL = "claude-sonnet-4-20250514"


# ── Context builder ───────────────────────────────────────────────────────────

def build_prompt_context(run: QueryRun, db: Session) -> dict:
    """
    Assemble all data needed for content generation into a single context dict.
    Passed to both blog post and social post generation prompts.
    """
    run_month = run.run_date.strftime("%B %Y") if run.run_date else "Unknown"
    run_month_slug = run.run_date.strftime("%Y-%m") if run.run_date else "unknown"

    # Top 10 overall (cross-platform, cross-vertical, all platforms combined)
    top_rows = (
        db.query(CitationIndex)
        .filter_by(run_id=run.id, platform_slug="all", vertical_slug=None)
        .order_by(CitationIndex.rank)
        .limit(15)
        .all()
    )

    # Biggest platform gap (sorted by abs perplexity_vs_chatgpt_delta)
    gap_rows = (
        db.query(CitationIndex)
        .filter(
            CitationIndex.run_id == run.id,
            CitationIndex.platform_slug == "all",
            CitationIndex.perplexity_vs_chatgpt_delta.isnot(None),
        )
        .order_by(CitationIndex.perplexity_vs_chatgpt_delta)  # most negative first
        .limit(5)
        .all()
    )

    # Archetype changes
    archetype_changes = (
        db.query(ArchetypeSnapshot)
        .filter_by(run_id=run.id, archetype_changed=True)
        .all()
    )

    # Per-vertical top 5
    verticals_data = {}
    vertical_slugs = [
        r[0] for r in db.query(CitationIndex.vertical_slug)
        .filter(
            CitationIndex.run_id == run.id,
            CitationIndex.platform_slug == "all",
            CitationIndex.vertical_slug.isnot(None),
        )
        .distinct()
        .all()
    ]

    for vslug in vertical_slugs:
        v_rows = (
            db.query(CitationIndex)
            .filter_by(run_id=run.id, platform_slug="all", vertical_slug=vslug)
            .order_by(CitationIndex.rank)
            .limit(5)
            .all()
        )
        verticals_data[vslug] = [
            {
                "rank": r.rank,
                "name": r.entity_name,
                "score": r.citation_score_normalised,
                "archetype_label": r.archetype_label_public or "—",
                "delta_rank": r.delta_rank,
                "trend": r.trend_direction,
            }
            for r in v_rows
        ]

    return {
        "run_month": run_month,
        "run_month_slug": run_month_slug,
        "run_date": run.run_date.strftime("%Y-%m-%d") if run.run_date else "unknown",
        "gap_analysis_valid": run.gap_analysis_valid,
        "platforms_run": run.platforms_run or [],
        "top_brands": [
            {
                "rank": r.rank,
                "name": r.entity_name,
                "score": r.citation_score_normalised,
                "archetype": r.citation_archetype,
                "archetype_label": r.archetype_label_public or "—",
                "chatgpt": r.chatgpt_score,
                "perplexity": r.perplexity_score,
                "gemini": r.gemini_score,
                "delta_perp_vs_gpt": r.perplexity_vs_chatgpt_delta,
                "delta_rank": r.delta_rank,
                "trend": r.trend_direction,
            }
            for r in top_rows
        ],
        "biggest_gaps": [
            {
                "name": r.entity_name,
                "chatgpt": r.chatgpt_score,
                "perplexity": r.perplexity_score,
                "delta": r.perplexity_vs_chatgpt_delta,
                "archetype_label": r.archetype_label_public or "—",
            }
            for r in gap_rows
        ],
        "archetype_changes": [
            {
                "brand_id": c.brand_id,
                "from": c.previous_archetype,
                "to": c.citation_archetype,
                "from_label": ARCHETYPE_PUBLIC_LABELS.get(c.previous_archetype or "", "—"),
                "to_label": ARCHETYPE_PUBLIC_LABELS.get(c.citation_archetype, "—"),
            }
            for c in archetype_changes
        ],
        "verticals": verticals_data,
    }


# ── Blog post generation ──────────────────────────────────────────────────────

_BLOG_PROMPT = """You are writing the monthly GEO Brand Citation Index report for The GEO Lab (thegeolab.net).

The GEO Brand Citation Index measures which brands ChatGPT, Perplexity, and Gemini recommend — and crucially, how those recommendations differ across platforms.

The core insight: ChatGPT answers from training data (model memory). Perplexity retrieves from the live web. The gap between them reveals which brands are living on AI memory vs winning on current relevance.

Five archetypes:
- 👑 Dominant Brand: high everywhere, low variance
- 🧠 AI Memory Brand: ChatGPT high, Perplexity significantly lower  
- 🔍 Live Search Brand: Perplexity high, ChatGPT lower
- 🫥 Fading Brand: moderate ChatGPT, near-zero Perplexity (alarming signal)
- ⭐ GEO Outlier: consistently cited beyond what domain authority predicts

RUN DATA:
{context_json}

INSTRUCTIONS:
Write a full blog post in markdown. AJ will add one personal commentary paragraph — write a [COMMENTARY PLACEHOLDER] marker where it should go (after the top findings section).

Structure:
1. H2: "What we measured" — 2 sentences: N brands, N queries, 3 platforms, run date
2. H2: "Top 10 most cited brands — {run_month}" — ranked table with Name | Archetype | ChatGPT | Perplexity | Gemini | Delta columns
3. H2: "This month's biggest platform gap" — 2-3 paragraphs naming the specific brand with the largest ChatGPT vs Perplexity divergence, real numbers, what it means
4. [COMMENTARY PLACEHOLDER]
5. H2: "Archetype spotlight: AI Memory Brands" — paragraph on the training_dependent brands in this run, why it matters for those brands' teams
6. H2: "Biggest movers" — table of brands that changed rank significantly or changed archetype
7. H2: "Vertical breakdown" — one subsection per vertical, top 5 brands with their archetype labels
8. H2: "Full data tables" — complete ranking tables per vertical per platform
9. H2: "Methodology" — 2 sentences linking to /geo-brand-citation-index/methodology/

Rules:
- Use real brand names and real numbers from the data. No hedging.
- Write in AJ's voice: research-oriented, direct, first-person where natural ("We ran...", "The data shows...").
- Every archetype label must match exactly (👑 Dominant Brand, 🧠 AI Memory Brand, etc.)
- This is publishable content — write to that standard.
- Output only the markdown. No preamble, no explanation outside the post."""


def generate_blog_post(context: dict, client: anthropic.Anthropic) -> str:
    prompt = _BLOG_PROMPT.format(
        context_json=json.dumps(context, indent=2, default=str),
        run_month=context["run_month"],
    )
    response = client.messages.create(
        model=GENERATION_MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


# ── Social posts generation ───────────────────────────────────────────────────

_SOCIAL_PROMPT = """You are writing 5 social media posts for The GEO Lab's monthly GEO Brand Citation Index report.

The index measures which brands AI platforms recommend and — crucially — why the gap between ChatGPT and Perplexity tells you more than any ranking alone.

RUN DATA:
{context_json}

REPORT URL: https://thegeolab.net/geo-brand-citation-index/{run_month_slug}/

Write exactly 5 posts. Separate each with ---

POST 1 — LinkedIn (Day 1): Report announcement. Lead with the single most striking finding. 150-200 words. End with the report URL.

POST 2 — Twitter/X (Day 2): AI Memory Brand spotlight. Pick the most interesting training_dependent brand. Short thread format (Tweet 1 / Tweet 2 / Tweet 3). Max 280 chars per tweet. Real numbers.

POST 3 — LinkedIn (Day 5): Platform divergence insight. Focus on the biggest ChatGPT vs Perplexity gap — what it means for that brand's team. 100-150 words.

POST 4 — Twitter/X (Day 9): Biggest mover. Which brand gained or lost most since last month. 1-2 tweets. Punchy.

POST 5 — LinkedIn (Day 14): Methodology/credibility post. Explain how the index works in plain language. Why the gap matters more than the ranking. 100-120 words. End with the report URL.

Rules:
- Real brand names, real numbers. No placeholders.
- AJ's voice: direct, research-oriented, not promotional.
- Each post must be immediately usable — no edits needed except AJ's optional personal touch.
- Output only the 5 posts separated by ---. No preamble."""


def generate_social_posts(context: dict, client: anthropic.Anthropic) -> str:
    prompt = _SOCIAL_PROMPT.format(
        context_json=json.dumps(context, indent=2, default=str),
        run_month_slug=context["run_month_slug"],
    )
    response = client.messages.create(
        model=GENERATION_MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_monthly_report(run: QueryRun, db: Session) -> dict:
    """
    Generate all monthly content assets from run data.

    Returns dict of output file paths.
    Output structure: outputs/YYYY-MM/
      report_YYYY-MM.md
      social_posts_YYYY-MM.txt
      report_brief_YYYY-MM.txt   (context used for generation — for audit)
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    run_month_slug = run.run_date.strftime("%Y-%m") if run.run_date else "unknown"

    out_dir = Path(OUTPUTS_DIR) / run_month_slug
    out_dir.mkdir(parents=True, exist_ok=True)

    log.info("Building content generation context...")
    context = build_prompt_context(run, db)

    # Save brief for audit trail
    brief_path = out_dir / f"report_brief_{run_month_slug}.txt"
    brief_path.write_text(json.dumps(context, indent=2, default=str))
    log.info(f"Brief saved: {brief_path}")

    log.info("Generating blog post...")
    blog_post = generate_blog_post(context, client)
    blog_path = out_dir / f"report_{run_month_slug}.md"
    blog_path.write_text(blog_post)
    log.info(f"Blog post saved: {blog_path}")

    log.info("Generating social posts...")
    social = generate_social_posts(context, client)
    social_path = out_dir / f"social_posts_{run_month_slug}.txt"
    social_path.write_text(social)
    log.info(f"Social posts saved: {social_path}")

    run.report_generated = True
    db.commit()

    return {
        "blog_post": str(blog_path),
        "social_posts": str(social_path),
        "brief": str(brief_path),
        "run_month": run_month_slug,
    }
