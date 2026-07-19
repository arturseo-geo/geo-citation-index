"""
run_monthly.py — single entry point for the GEO Citation Index monthly pipeline.

Usage:
    python run_monthly.py               # Full run
    python run_monthly.py --dry-run     # Validate config, no queries sent
    python run_monthly.py --content-only # Regenerate content from last run's data
    python run_monthly.py --skip-pdf    # Skip PDF generation

Pipeline steps:
    1. Run queries (ChatGPT + Gemini server-side; Perplexity via browser)
    2. Extract brands from responses
    3. Score citations, compute deltas, classify archetypes
    4. Build citation index
    5. Export index JSON
    6. Generate blog post + social posts (Anthropic API)
    7. Generate PDF report (ReportLab)

Keep the browser tab open when prompted for Perplexity.
Output files are written to outputs/YYYY-MM/.
"""

import argparse
import http.server
import json
import logging
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)



def capture_provenance():
    """Capture git state + instrument config at run time."""
    import subprocess
    from app.core.config import (
        OPENAI_MODEL, GEMINI_MODEL, PERPLEXITY_MODEL,
        POSITION_WEIGHTS, POSITION_WEIGHT_DEFAULT, URL_CITED_BONUS,
    )

    # Git state
    try:
        git_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        git_commit = None

    # Code-file dirtiness: only app/ and run_monthly.py count as "dirty"
    # for instrument-provenance purposes. Knowledge/data file changes do
    # not affect the pipeline's behaviour.
    # Let git do the pathspec filtering rather than manual offset parsing.
    git_dirty = None
    dirty_detail = None
    try:
        # Pathspec-filtered: dirty only if pipeline code is modified
        code_porcelain = subprocess.check_output(
            ["git", "status", "--porcelain", "--", "app/", "run_monthly.py"],
            text=True, stderr=subprocess.DEVNULL
        ).strip()
        git_dirty = bool(code_porcelain)

        # Build path lists from NUL-separated output (handles renames,
        # spaces in paths, and quoted filenames without manual offset parsing).
        def _parse_porcelain_z(*pathspec):
            cmd = ["git", "status", "--porcelain", "-z"]
            if pathspec:
                cmd += ["--"] + list(pathspec)
            raw = subprocess.check_output(
                cmd, text=True, stderr=subprocess.DEVNULL
            )
            paths = set()
            entries = raw.split("\0")
            i = 0
            while i < len(entries):
                e = entries[i]
                if not e:
                    i += 1
                    continue
                status = e[:2]
                p = e[3:]
                paths.add(p)
                # Renames (R/C) have a second NUL-separated entry for the old name
                if status[0] in ("R", "C"):
                    i += 1
                    if i < len(entries) and entries[i]:
                        paths.add(entries[i])
                i += 1
            return paths

        code_paths = _parse_porcelain_z("app/", "run_monthly.py")
        all_paths = _parse_porcelain_z()
        non_code_paths = sorted(all_paths - code_paths)

        dirty_detail = {
            "code_files_dirty": git_dirty,
            "code_files": sorted(code_paths),
            "non_code_dirty_paths": non_code_paths,
        }
    except Exception:
        git_dirty = None
        dirty_detail = {"error": "git status failed; dirtiness undetermined"}

    provenance = {
        "arms": {
            "chatgpt": {
                "endpoint": "openai Python SDK (client.chat.completions.create)",
                "model_string": OPENAI_MODEL,
                "retrieval_enabled": False,
            },
            "gemini": {
                "endpoint": "google-generativeai SDK (genai.GenerativeModel.generate_content)",
                "model_string": GEMINI_MODEL,
                "retrieval_enabled": False,
            },
            "perplexity": {
                "endpoint": "https://api.perplexity.ai/chat/completions",
                "model_string": PERPLEXITY_MODEL,
                "retrieval_enabled": True,
            },
        },
        "scoring_config": {
            "position_weights": POSITION_WEIGHTS,
            "position_weight_default": POSITION_WEIGHT_DEFAULT,
            "url_bonus": URL_CITED_BONUS,
        },
        "captured_at": datetime.utcnow().isoformat() + "Z",
    }

    if dirty_detail:
        provenance["git_dirty_detail"] = dirty_detail

    return git_commit, git_dirty, provenance

def parse_args():
    p = argparse.ArgumentParser(description="GEO Citation Index monthly pipeline")
    p.add_argument("--dry-run",      action="store_true", help="Validate config only")
    p.add_argument("--content-only", action="store_true", help="Regenerate content from last run")
    p.add_argument("--skip-pdf",     action="store_true", help="Skip PDF generation")
    p.add_argument("--browser-mode", action="store_true", help="Use browser (Puter.js) for ChatGPT instead of API (no API key needed)")
    return p.parse_args()


def validate_config(browser_mode: bool = False):
    """Check all required env vars and DB connectivity."""
    from app.core.config import OPENAI_API_KEY, GOOGLE_API_KEY, ANTHROPIC_API_KEY, PERPLEXITY_API_KEY
    errors = []

    if not OPENAI_API_KEY:
        errors.append("OPENAI_API_KEY not set")
    if not GOOGLE_API_KEY:
        errors.append("GOOGLE_API_KEY not set")
    if not ANTHROPIC_API_KEY:
        errors.append("ANTHROPIC_API_KEY not set")
    if not PERPLEXITY_API_KEY:
        errors.append("PERPLEXITY_API_KEY not set")

    try:
        from app.models.db_engine import init_db, SessionLocal
        from app.models.db import Platform
        init_db()
        db = SessionLocal()
        count = db.query(Platform).count()
        db.close()
        if count == 0:
            errors.append("Database not seeded. Run: python scripts/seed_dictionary.py")
    except Exception as e:
        errors.append(f"Database error: {e}")

    return errors


def wait_for_browser_queries(run_id: str, queries: list, platform: str, expected_count: int, port: int = 5679, timeout: int = 600):
    """
    Start a local HTTP server to receive results from browser components (Puter.js).
    Opens the browser automatically with the runner page.
    Blocks until all results are received or timeout is reached.

    Args:
        platform: 'perplexity' or 'chatgpt'
    """
    from app.models.db_engine import SessionLocal
    from app.services.query_runner import merge_perplexity_results, merge_chatgpt_browser_results

    results_received = []
    done_event = threading.Event()

    runner_file = f"frontend/{platform}_runner.html"
    endpoint = f"/{platform}-results"
    merge_fn = merge_chatgpt_browser_results if platform == "chatgpt" else merge_perplexity_results

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_OPTIONS(self):
            # Handle CORS preflight
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_POST(self):
            # Check path (strip query string if present)
            path = self.path.split("?")[0]
            log.info(f"Received POST to {path}")

            if path == endpoint:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                try:
                    data = json.loads(body)
                    received = data.get("results", [])
                    results_received.extend(received)
                    log.info(f"Received {len(received)} results, total: {len(results_received)}/{expected_count}")

                    self.send_response(200)
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"status":"ok"}')

                    if len(results_received) >= expected_count:
                        done_event.set()
                except Exception as e:
                    log.error(f"Error processing POST: {e}")
                    self.send_response(400)
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
            else:
                log.warning(f"Unknown endpoint: {path}")
                self.send_response(404)
                self.end_headers()

        def do_GET(self):
            # Serve the runner HTML with injected queries
            runner_path = Path(runner_file)
            if runner_path.exists():
                content = runner_path.read_text()

                # Inject queries and config into the HTML - BEFORE other scripts
                query_json = json.dumps([q.query_text for q in queries])
                inject_script = f"""
    <script>
        // Injected by run_monthly.py
        window.CHATGPT_QUERIES = {query_json};
        window.CHATGPT_RUN_ID = "{run_id}";
        window.CHATGPT_CALLBACK_URL = "http://127.0.0.1:{port}{endpoint}";
        window.PERPLEXITY_QUERIES = {query_json};
        window.PERPLEXITY_RUN_ID = "{run_id}";
    </script>
"""
                # Insert right after <head> so it runs first
                content = content.replace("<head>", "<head>" + inject_script)

                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(content.encode())
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            pass  # Suppress default HTTP server logs

    server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()

    log.info(f"Opening {platform.title()} runner in browser...")
    log.info(f"Keep the browser tab open until all {expected_count} queries complete.")
    webbrowser.open(f"http://127.0.0.1:{port}/?run_id={run_id}")

    done_event.wait(timeout=timeout)
    server.shutdown()

    if results_received:
        db = SessionLocal()
        try:
            merged = merge_fn(run_id, results_received, db)
            log.info(f"Merged {merged} {platform.title()} results.")
        finally:
            db.close()
    else:
        log.warning(f"No {platform.title()} results received within timeout.")


def wait_for_perplexity(run_id: str, queries: list, expected_count: int, port: int = 5679, timeout: int = 600):
    """Wrapper for backward compatibility."""
    wait_for_browser_queries(run_id, queries, "perplexity", expected_count, port, timeout)


def run_full_pipeline(args):
    from app.models.db_engine import init_db, SessionLocal
    from app.models.db import QueryRun, QueryPanel
    from app.services.query_runner import run_server_side_queries
    from app.core.brand_extractor import extract_brands_from_run
    from app.core.citation_scorer import compute_brand_scores
    from app.core.index_builder import build_citation_index, export_index_json, export_provenance_json
    from app.core.content_generator import generate_monthly_report
    from app.services.report_writer import generate_pdf_report
    from app.core.config import ARCHETYPE_THRESHOLD_VERSION
    from datetime import timezone

    init_db()
    db = SessionLocal()

    try:
        # Get active panel
        panel = db.query(QueryPanel).filter_by(slug="v1-panel", is_active=True).first()
        if not panel:
            log.error("No active panel found. Run: python scripts/seed_dictionary.py")
            sys.exit(1)

        queries = [q for q in panel.queries if q.is_active]
        query_count = len(queries)
        log.info(f"Panel: {panel.name} | {query_count} queries | 3 platforms")

        # Create run record
        run = QueryRun(
            panel_id=panel.id,
            label=f"Monthly run {datetime.now(timezone.utc).strftime('%Y-%m')}",
            status="pending",
            run_date=datetime.now(timezone.utc),
            total_queries=query_count * 3,  # 3 platforms
            archetype_threshold_version=ARCHETYPE_THRESHOLD_VERSION,
        )
        # Capture provenance before any queries fire
        git_commit, git_dirty, provenance = capture_provenance()
        if git_commit is None:
            log.error("Provenance capture failed: no git HEAD. Aborting.")
            sys.exit(1)
        run.git_commit = git_commit
        run.git_dirty = git_dirty
        run.provenance_json = provenance
        db.add(run)
        db.commit()
        log.info(f"Run created: {run.id} (commit: {git_commit[:8] if git_commit else 'unknown'}, dirty: {git_dirty})")

        # Step 1: Run all queries via API (ChatGPT + Gemini + Perplexity)
        log.info("=" * 50)
        log.info("STEP 1/6: Running queries via API (ChatGPT + Gemini + Perplexity)...")
        run_server_side_queries(run, db)

        run.status = "complete"
        db.commit()

        # Step 2: Brand extraction
        log.info("=" * 50)
        log.info("STEP 2/6: Extracting brands from responses...")
        extraction_run = extract_brands_from_run(run, db)
        log.info(f"Brands found: {extraction_run.brands_found} | New: {extraction_run.new_brands_discovered}")

        # Step 3: Citation scoring + archetypes
        log.info("=" * 50)
        log.info("STEP 3/6: Computing citation scores and archetypes...")
        compute_brand_scores(run, db)
        log.info(f"Gap analysis valid: {run.gap_analysis_valid}")

        # Step 4: Build index
        log.info("=" * 50)
        log.info("STEP 4/6: Building citation index...")
        build_citation_index(run, db)

        # Step 5: Export JSON
        log.info("=" * 50)
        log.info("STEP 5/6: Exporting index JSON...")
        json_path = export_index_json(run, db)
        log.info(f"JSON: {json_path}")

        prov_path = export_provenance_json(run)
        log.info(f"Provenance: {prov_path}")

        # Step 6: Content generation
        log.info("=" * 50)
        log.info("STEP 6/6: Generating report and social posts...")
        content = generate_monthly_report(run, db)

        # PDF
        if not args.skip_pdf:
            pdf_path = generate_pdf_report(run, db)
            if pdf_path:
                log.info(f"PDF: {pdf_path}")

        # Summary
        run_month = run.run_date.strftime("%Y-%m")
        log.info("=" * 50)
        log.info("PIPELINE COMPLETE")
        log.info(f"Output directory: outputs/{run_month}/")
        log.info(f"  Blog post:    {content['blog_post']}")
        log.info(f"  Social posts: {content['social_posts']}")
        log.info(f"  Index JSON:   {json_path}")
        log.info("")
        log.info("Next steps:")
        log.info("  1. Review and add one paragraph to the blog post")
        log.info("  2. Skim the 5 social posts — adjust tone if needed")
        log.info("  3. Paste blog post into WordPress")
        log.info("  4. Upload index JSON to WordPress media library")
        log.info("  5. Schedule social posts")

    finally:
        db.close()


def run_content_only():
    """Regenerate content assets from the most recent completed run."""
    from app.models.db_engine import SessionLocal
    from app.models.db import QueryRun
    from app.core.content_generator import generate_monthly_report
    from app.core.index_builder import export_index_json
    from app.services.report_writer import generate_pdf_report

    db = SessionLocal()
    try:
        run = (
            db.query(QueryRun)
            .filter_by(status="complete")
            .order_by(QueryRun.run_date.desc())
            .first()
        )
        if not run:
            log.error("No completed runs found.")
            sys.exit(1)

        log.info(f"Regenerating content for run {run.id} ({run.run_date})")
        content = generate_monthly_report(run, db)
        json_path = export_index_json(run, db)
        generate_pdf_report(run, db)

        log.info("Content regenerated.")
        log.info(f"  Blog post:  {content['blog_post']}")
        log.info(f"  Social:     {content['social_posts']}")
        log.info(f"  JSON:       {json_path}")
    finally:
        db.close()


def main():
    args = parse_args()

    print("\nGEO Brand Citation Index — Monthly Pipeline")
    print("=" * 50)

    # Always validate first
    errors = validate_config()
    if errors:
        for e in errors:
            log.error(f"Config error: {e}")
        sys.exit(1)
    log.info("Config validated. All API keys present.")

    if args.dry_run:
        log.info("Dry run complete. All checks passed.")
        sys.exit(0)

    if args.content_only:
        run_content_only()
        sys.exit(0)

    run_full_pipeline(args)


if __name__ == "__main__":
    main()
