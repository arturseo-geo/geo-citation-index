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


def parse_args():
    p = argparse.ArgumentParser(description="GEO Citation Index monthly pipeline")
    p.add_argument("--dry-run",      action="store_true", help="Validate config only")
    p.add_argument("--content-only", action="store_true", help="Regenerate content from last run")
    p.add_argument("--skip-pdf",     action="store_true", help="Skip PDF generation")
    return p.parse_args()


def validate_config():
    """Check all required env vars and DB connectivity."""
    from app.core.config import OPENAI_API_KEY, GOOGLE_API_KEY, ANTHROPIC_API_KEY
    errors = []
    if not OPENAI_API_KEY:
        errors.append("OPENAI_API_KEY not set")
    if not GOOGLE_API_KEY:
        errors.append("GOOGLE_API_KEY not set")
    if not ANTHROPIC_API_KEY:
        errors.append("ANTHROPIC_API_KEY not set")

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


def wait_for_perplexity(run_id: str, expected_count: int, port: int = 5679, timeout: int = 600):
    """
    Start a local HTTP server to receive Perplexity results from the browser component.
    Opens the browser automatically with the runner page.
    Blocks until all results are received or timeout is reached.
    """
    from app.models.db_engine import SessionLocal
    from app.services.query_runner import merge_perplexity_results

    results_received = []
    done_event = threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path == "/perplexity-results":
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                try:
                    data = json.loads(body)
                    results_received.extend(data.get("results", []))
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'{"status":"ok"}')
                    if len(results_received) >= expected_count:
                        done_event.set()
                except Exception:
                    self.send_response(400)
                    self.end_headers()
            else:
                self.send_response(404)
                self.end_headers()

        def do_GET(self):
            # Serve the Perplexity runner HTML
            runner_path = Path("frontend/perplexity_runner.html")
            if runner_path.exists():
                content = runner_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            pass  # Suppress default HTTP server logs

    server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()

    log.info(f"Opening Perplexity runner in browser...")
    log.info(f"Keep the browser tab open until all {expected_count} queries complete.")
    webbrowser.open(f"http://127.0.0.1:{port}/?run_id={run_id}")

    done_event.wait(timeout=timeout)
    server.shutdown()

    if results_received:
        db = SessionLocal()
        try:
            merged = merge_perplexity_results(run_id, results_received, db)
            log.info(f"Merged {merged} Perplexity results.")
        finally:
            db.close()
    else:
        log.warning("No Perplexity results received within timeout.")


def run_full_pipeline(args):
    from app.models.db_engine import init_db, SessionLocal
    from app.models.db import QueryRun, QueryPanel
    from app.services.query_runner import run_server_side_queries
    from app.core.brand_extractor import extract_brands_from_run
    from app.core.citation_scorer import compute_brand_scores
    from app.core.index_builder import build_citation_index, export_index_json
    from app.core.content_generator import generate_monthly_report
    from app.services.report_writer import generate_pdf_report
    from app.core.config import ARCHETYPE_THRESHOLD_VERSION

    init_db()
    db = SessionLocal()

    try:
        # Get active panel
        panel = db.query(QueryPanel).filter_by(slug="v1-panel", is_active=True).first()
        if not panel:
            log.error("No active panel found. Run: python scripts/seed_dictionary.py")
            sys.exit(1)

        query_count = len([q for q in panel.queries if q.is_active])
        log.info(f"Panel: {panel.name} | {query_count} queries | 3 platforms")

        # Create run record
        run = QueryRun(
            panel_id=panel.id,
            label=f"Monthly run {datetime.utcnow().strftime('%Y-%m')}",
            status="pending",
            run_date=datetime.utcnow(),
            total_queries=query_count * 3,  # 3 platforms
            archetype_threshold_version=ARCHETYPE_THRESHOLD_VERSION,
        )
        db.add(run)
        db.commit()
        log.info(f"Run created: {run.id}")

        # Step 1: Server-side queries (ChatGPT + Gemini)
        log.info("=" * 50)
        log.info("STEP 1/6: Running ChatGPT + Gemini queries...")
        run_server_side_queries(run, db)

        # Step 1b: Perplexity (browser)
        log.info("=" * 50)
        log.info("STEP 1b: Waiting for Perplexity browser queries...")
        wait_for_perplexity(run.id, expected_count=query_count)

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
    log.info("Config validated.")

    if args.dry_run:
        log.info("Dry run complete. All checks passed.")
        sys.exit(0)

    if args.content_only:
        run_content_only()
        sys.exit(0)

    run_full_pipeline(args)


if __name__ == "__main__":
    main()
