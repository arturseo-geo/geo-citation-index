"""
Seed script — one-time setup for platforms, verticals, brands, and queries.

Run this before the first monthly run:
    python scripts/seed_dictionary.py

Safe to re-run — uses get_or_create patterns throughout.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.db_engine import init_db, SessionLocal
from app.models.db import Platform, QueryVertical, Brand, BrandDictionaryEntry, QueryPanel, PanelQuery
from app.core.config import PLATFORMS, VERTICALS, ARCHETYPE_THRESHOLD_VERSION


def get_or_create(db, model, defaults=None, **kwargs):
    instance = db.query(model).filter_by(**kwargs).first()
    if instance:
        return instance, False
    params = {**kwargs, **(defaults or {})}
    instance = model(**params)
    db.add(instance)
    db.flush()
    return instance, True


def seed_platforms(db):
    print("Seeding platforms...")
    for p in PLATFORMS:
        obj, created = get_or_create(db, Platform, slug=p["slug"], defaults={
            "display_name": p["display_name"],
            "model_name": p["model_name"],
            "api_type": p["api_type"],
            "retrieval_type": p["retrieval_type"],
        })
        if created:
            print(f"  + {p['display_name']}")


def seed_verticals(db):
    print("Seeding verticals...")
    for v in VERTICALS:
        obj, created = get_or_create(db, QueryVertical, slug=v["slug"], defaults={
            "display_name": v["display_name"],
            "sort_order": v["sort_order"],
        })
        if created:
            print(f"  + {v['display_name']}")


def seed_brands(db):
    print("Seeding v1 brand dictionary...")

    seo_vertical = db.query(QueryVertical).filter_by(slug="seo-marketing").first()
    crm_vertical = db.query(QueryVertical).filter_by(slug="crm-sales").first()
    ai_vertical  = db.query(QueryVertical).filter_by(slug="ai-llm-tools").first()

    brand_data = {
        "seo-marketing": [
            ("Ahrefs",           "ahrefs",           ["ahrefs.com"]),
            ("Semrush",          "semrush",           ["semrush", "SEMrush"]),
            ("Moz",              "moz",               ["moz.com", "Moz Pro"]),
            ("Surfer SEO",       "surfer-seo",        ["SurferSEO", "Surfer"]),
            ("Clearscope",       "clearscope",        []),
            ("Screaming Frog",   "screaming-frog",    ["Screaming Frog SEO Spider"]),
            ("SE Ranking",       "se-ranking",        ["seranking"]),
            ("Mangools",         "mangools",          ["KWFinder"]),
            ("Majestic",         "majestic",          ["Majestic SEO"]),
            ("Ubersuggest",      "ubersuggest",       []),
            ("Google Search Console", "google-search-console", ["GSC", "Search Console"]),
            ("Rank Math",        "rank-math",         ["RankMath"]),
            ("Yoast SEO",        "yoast-seo",         ["Yoast"]),
        ],
        "crm-sales": [
            ("Salesforce",       "salesforce",        ["SFDC", "Salesforce CRM"]),
            ("HubSpot",          "hubspot",           ["HubSpot CRM"]),
            ("Pipedrive",        "pipedrive",         []),
            ("Zoho CRM",         "zoho-crm",          ["Zoho"]),
            ("Monday.com",       "monday-crm",        ["monday CRM"]),
            ("Freshsales",       "freshsales",        ["Freshworks CRM"]),
            ("Close CRM",        "close-crm",         ["Close.io", "Close"]),
            ("Attio",            "attio",             []),
            ("Copper",           "copper",            ["Copper CRM"]),
            ("SugarCRM",         "sugarcrm",          ["Sugar CRM"]),
            ("Insightly",        "insightly",         []),
            ("Keap",             "keap",              ["Infusionsoft"]),
        ],
        "ai-llm-tools": [
            ("ChatGPT",          "chatgpt",           ["GPT-4", "GPT-4o", "OpenAI"]),
            ("Claude",           "claude",            ["Claude AI", "Anthropic Claude"]),
            ("Gemini",           "gemini",            ["Google Gemini", "Bard"]),
            ("Perplexity",       "perplexity",        ["Perplexity AI"]),
            ("Copilot",          "copilot",           ["GitHub Copilot", "Microsoft Copilot"]),
            ("Cursor",           "cursor",            ["Cursor IDE", "Cursor AI"]),
            ("Jasper",           "jasper",            ["Jasper AI"]),
            ("Copy.ai",          "copy-ai",           ["CopyAI"]),
            ("Writesonic",       "writesonic",        []),
            ("Midjourney",       "midjourney",        []),
            ("Runway",           "runway",            ["Runway ML"]),
            ("Notion AI",        "notion-ai",         ["Notion"]),
            ("Grammarly",        "grammarly",         []),
        ],
    }

    vertical_map = {
        "seo-marketing": seo_vertical,
        "crm-sales": crm_vertical,
        "ai-llm-tools": ai_vertical,
    }

    total = 0
    for vertical_slug, brands in brand_data.items():
        vertical = vertical_map.get(vertical_slug)
        if not vertical:
            continue
        for canonical_name, slug, aliases in brands:
            brand, created = get_or_create(db, Brand, slug=slug, defaults={
                "canonical_name": canonical_name,
                "aliases": aliases,
                "vertical_id": vertical.id,
                "source": "dictionary",
                "is_verified": True,
            })
            if created:
                total += 1

            # Seed dictionary entries for canonical name and aliases
            for term in [canonical_name] + aliases:
                get_or_create(db, BrandDictionaryEntry,
                    vertical_id=vertical.id, term=term,
                    defaults={"brand_id": brand.id, "is_alias": (term != canonical_name)})

    print(f"  + {total} brands seeded")


def seed_queries(db):
    print("Seeding v1 query panel...")

    seo = db.query(QueryVertical).filter_by(slug="seo-marketing").first()
    crm = db.query(QueryVertical).filter_by(slug="crm-sales").first()
    ai  = db.query(QueryVertical).filter_by(slug="ai-llm-tools").first()

    panel, created = get_or_create(db, QueryPanel, slug="v1-panel", defaults={
        "name": "GEO Citation Index v1",
        "version": "1.0",
        "description": "Monthly citation tracking across 3 verticals, 25 queries, 3 platforms.",
        "requires_all_platforms": True,
        "rerun_cadence_days": 30,
    })
    if created:
        print("  + Panel: GEO Citation Index v1")

    queries = [
        # SEO & Marketing (6 queries)
        ("What are the best SEO tools available right now?",                      "recommendation", seo, False),
        ("What are the best tools for keyword research?",                         "recommendation", seo, False),
        ("What is the best SEO tool for a small business?",                       "best_for",       seo, False),
        ("What is the best SEO tool for enterprise teams?",                       "best_for",       seo, False),
        ("Which SEO platforms are most widely used by professionals?",             "category_open",  seo, False),
        ("What are the best SEO tools in 2026?",                                   "temporal",       seo, False),
        # CRM & Sales (6 queries)
        ("What are the best CRM tools available right now?",                      "recommendation", crm, False),
        ("What CRM do most sales teams use?",                                     "category_open",  crm, False),
        ("What is the best CRM for a small business?",                            "best_for",       crm, False),
        ("What is the best CRM for enterprise sales teams?",                      "best_for",       crm, False),
        ("Compare Salesforce vs HubSpot — which is better?",                      "comparison",     crm, False),
        ("What are the best CRM tools in 2026?",                                   "temporal",       crm, False),
        # AI & LLM Tools (6 queries)
        ("What are the best AI writing tools available right now?",               "recommendation", ai,  False),
        ("What are the most popular AI tools for businesses?",                    "category_open",  ai,  False),
        ("What is the best AI tool for content creation?",                        "best_for",       ai,  False),
        ("What is the best AI coding assistant?",                                 "best_for",       ai,  False),
        ("Compare ChatGPT vs Claude — which is better for writing?",              "comparison",     ai,  True),  # bias_flag
        ("What are the most useful AI tools in 2026?",                             "temporal",       ai,  False),
    ]

    for i, (text, intent, vertical, bias) in enumerate(queries):
        pq, created = get_or_create(
            db, PanelQuery,
            panel_id=panel.id, query_text=text,
            defaults={
                "vertical_id": vertical.id if vertical else None,
                "intent_type": intent,
                "bias_flag": bias,
                "sort_order": i,
            }
        )
        if created:
            print(f"  + [{intent}] {text[:60]}...")

    panel.query_count = db.query(PanelQuery).filter_by(panel_id=panel.id).count()
    db.commit()


def main():
    print("Initialising database...")
    init_db()

    db = SessionLocal()
    try:
        seed_platforms(db)
        seed_verticals(db)
        seed_brands(db)
        seed_queries(db)
        db.commit()
        print("\nSeed complete. Ready to run: python run_monthly.py")
    finally:
        db.close()


if __name__ == "__main__":
    main()
