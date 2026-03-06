"""
Query Runner — executes panel queries against ChatGPT and Gemini.

Perplexity runs separately in the browser via frontend/perplexity_runner.html
(Puter.js, no API key required). Results are submitted to a local HTTP
endpoint and merged into the run after browser queries complete.

Usage:
    from app.services.query_runner import run_server_side_queries
    run_server_side_queries(run, db)
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import (
    OPENAI_API_KEY, OPENAI_MODEL,
    GOOGLE_API_KEY, GEMINI_MODEL,
    PERPLEXITY_API_KEY, PERPLEXITY_MODEL,
    GEMINI_RATE_LIMIT_DELAY_SECONDS,
)
from app.models.db import QueryRun, RunResult, PanelQuery, Platform

log = logging.getLogger(__name__)


# ── ChatGPT ───────────────────────────────────────────────────────────────────

def _run_chatgpt_query(query_text: str) -> tuple[Optional[str], Optional[str]]:
    """
    Run a single query against ChatGPT via OpenAI API.
    Returns (response_text, error_message).
    """
    try:
        import openai
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": query_text}],
            max_tokens=800,
            temperature=0.3,  # Lower temp for more reproducible responses
        )
        return resp.choices[0].message.content, None
    except Exception as e:
        return None, str(e)


# ── Gemini ────────────────────────────────────────────────────────────────────

def _run_gemini_query(query_text: str) -> tuple[Optional[str], Optional[str]]:
    """
    Run a single query against Gemini via Google AI Studio API.
    Returns (response_text, error_message).

    Rate limit: free tier is 15 req/min. Caller must enforce
    GEMINI_RATE_LIMIT_DELAY_SECONDS between calls.
    """
    try:
        import google.generativeai as genai
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(query_text)
        return response.text, None
    except Exception as e:
        return None, str(e)


# ── Perplexity ────────────────────────────────────────────────────────────────

def _run_perplexity_query(query_text: str) -> tuple[Optional[str], Optional[str]]:
    """
    Run a single query against Perplexity API.
    Returns (response_text, error_message).

    Perplexity uses OpenAI-compatible API format.
    """
    try:
        import requests
        headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": PERPLEXITY_MODEL,
            "messages": [{"role": "user", "content": query_text}],
        }
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"], None
    except Exception as e:
        return None, str(e)


# ── Main runner ───────────────────────────────────────────────────────────────

def run_server_side_queries(run: QueryRun, db: Session, skip_chatgpt: bool = False, skip_perplexity: bool = False) -> None:
    """
    Execute all panel queries for ChatGPT, Gemini, and Perplexity.
    Writes RunResult rows for each (query, platform) pair.

    Gemini queries are rate-limited to GEMINI_RATE_LIMIT_DELAY_SECONDS
    between requests (free tier: 15 req/min).

    Args:
        skip_chatgpt: If True, skip ChatGPT queries (useful when API quota exceeded)
        skip_perplexity: If True, skip Perplexity queries (use browser instead)
    """
    panel = run.panel
    queries = [q for q in panel.queries if q.is_active]

    chatgpt_platform = db.query(Platform).filter_by(slug="chatgpt").first()
    gemini_platform  = db.query(Platform).filter_by(slug="gemini").first()
    perplexity_platform = db.query(Platform).filter_by(slug="perplexity").first()

    if not chatgpt_platform or not gemini_platform or not perplexity_platform:
        raise RuntimeError("Platform records not seeded. Run scripts/seed_dictionary.py first.")

    run.status = "running"
    db.commit()

    platforms_done = set(run.platforms_run or [])

    if skip_chatgpt:
        log.info("Skipping ChatGPT queries (--skip-chatgpt flag)")
    else:
        _run_platform_queries(run, queries, chatgpt_platform, _run_chatgpt_query, db, delay=0)
        platforms_done.add("chatgpt")

    _run_platform_queries(run, queries, gemini_platform, _run_gemini_query, db,
                          delay=GEMINI_RATE_LIMIT_DELAY_SECONDS)
    platforms_done.add("gemini")

    if skip_perplexity:
        log.info("Skipping Perplexity queries (browser mode)")
    else:
        log.info("Running Perplexity queries via API...")
        _run_platform_queries(run, queries, perplexity_platform, _run_perplexity_query, db, delay=1)
        platforms_done.add("perplexity")

    run.platforms_run = list(platforms_done)
    db.commit()
    log.info(f"Server-side queries complete for: {', '.join(platforms_done)}")


def _run_platform_queries(
    run: QueryRun,
    queries: list[PanelQuery],
    platform: Platform,
    query_fn,
    db: Session,
    delay: float = 0,
) -> None:
    log.info(f"Running {len(queries)} queries for {platform.display_name}...")
    for i, pq in enumerate(queries):
        if delay > 0 and i > 0:
            time.sleep(delay)

        start = time.time()
        response_text, error = query_fn(pq.query_text)
        latency_ms = int((time.time() - start) * 1000)

        result = RunResult(
            run_id=run.id,
            panel_query_id=pq.id,
            platform_id=platform.id,
            query_text=pq.query_text,
            response_text=response_text,
            status="complete" if response_text else "failed",
            error_message=error,
            latency_ms=latency_ms,
            executed_at=datetime.utcnow(),
        )
        db.add(result)

        run.completed_queries += (1 if response_text else 0)
        run.failed_queries    += (1 if error else 0)
        db.commit()

        if error:
            log.warning(f"[{platform.slug}] Query {pq.id} failed: {error}")


def merge_perplexity_results(
    run_id: str,
    results: list[dict],
    db: Session,
) -> int:
    """
    Merge Perplexity results submitted from the browser component.

    Expected result dict keys:
        query_text, response_text, cited_urls (list[str]), status, error_message

    Returns count of results merged.
    """
    run = db.query(QueryRun).get(run_id)
    if not run:
        raise ValueError(f"Run {run_id} not found.")

    perplexity = db.query(Platform).filter_by(slug="perplexity").first()
    if not perplexity:
        raise RuntimeError("Perplexity platform not seeded.")

    merged = 0
    for item in results:
        # Match to panel query by query_text
        pq = (
            db.query(PanelQuery)
            .filter_by(panel_id=run.panel_id)
            .filter(PanelQuery.query_text == item.get("query_text", ""))
            .first()
        )
        if not pq:
            log.warning(f"No matching panel query for: {item.get('query_text', '')[:60]}")
            continue

        result = RunResult(
            run_id=run.id,
            panel_query_id=pq.id,
            platform_id=perplexity.id,
            query_text=item.get("query_text", ""),
            response_text=item.get("response_text"),
            cited_urls=item.get("cited_urls", []),
            status=item.get("status", "complete"),
            error_message=item.get("error_message"),
            executed_at=datetime.utcnow(),
        )
        db.add(result)
        merged += 1

    platforms_done = set(run.platforms_run or [])
    platforms_done.add("perplexity")
    run.platforms_run = list(platforms_done)
    db.commit()
    log.info(f"Merged {merged} Perplexity results for run {run_id}.")
    return merged


def merge_chatgpt_browser_results(
    run_id: str,
    results: list[dict],
    db: Session,
) -> int:
    """
    Merge ChatGPT results submitted from the browser component (Puter.js).

    Expected result dict keys:
        query_text, response_text, latency_ms, error_message

    Returns count of results merged.
    """
    run = db.query(QueryRun).get(run_id)
    if not run:
        raise ValueError(f"Run {run_id} not found.")

    chatgpt = db.query(Platform).filter_by(slug="chatgpt").first()
    if not chatgpt:
        raise RuntimeError("ChatGPT platform not seeded.")

    merged = 0
    for item in results:
        # Match to panel query by query_text
        pq = (
            db.query(PanelQuery)
            .filter_by(panel_id=run.panel_id)
            .filter(PanelQuery.query_text == item.get("query_text", ""))
            .first()
        )
        if not pq:
            log.warning(f"No matching panel query for: {item.get('query_text', '')[:60]}")
            continue

        result = RunResult(
            run_id=run.id,
            panel_query_id=pq.id,
            platform_id=chatgpt.id,
            query_text=item.get("query_text", ""),
            response_text=item.get("response_text"),
            status="complete" if item.get("success") else "failed",
            error_message=item.get("error_message"),
            latency_ms=item.get("latency_ms"),
            executed_at=datetime.utcnow(),
        )
        db.add(result)

        if item.get("success"):
            run.completed_queries += 1
        else:
            run.failed_queries += 1
        merged += 1

    platforms_done = set(run.platforms_run or [])
    platforms_done.add("chatgpt")
    run.platforms_run = list(platforms_done)
    db.commit()
    log.info(f"Merged {merged} ChatGPT (browser) results for run {run_id}.")
    return merged
