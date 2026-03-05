"""
Report Writer — generates the monthly PDF report using ReportLab.

Output: outputs/YYYY-MM/report_YYYY-MM.pdf
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import ARCHETYPE_PUBLIC_LABELS, OUTPUTS_DIR
from app.models.db import CitationIndex, QueryRun

log = logging.getLogger(__name__)


def generate_pdf_report(run: QueryRun, db: Session) -> Optional[Path]:
    """
    Generate a PDF report from CitationIndex data for the completed run.
    Returns the output path, or None if ReportLab is not installed.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
        )
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
    except ImportError:
        log.warning("ReportLab not installed. Skipping PDF generation.")
        log.warning("Install with: pip install reportlab")
        return None

    run_month_slug = run.run_date.strftime("%Y-%m") if run.run_date else "unknown"
    run_month_name = run.run_date.strftime("%B %Y") if run.run_date else "Unknown"

    out_dir = Path(OUTPUTS_DIR) / run_month_slug
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"report_{run_month_slug}.pdf"

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title", parent=styles["Heading1"],
        fontSize=20, spaceAfter=6, textColor=colors.HexColor("#1a1a1a"),
    )
    h2_style = ParagraphStyle(
        "H2", parent=styles["Heading2"],
        fontSize=14, spaceAfter=4, textColor=colors.HexColor("#1a1a1a"),
    )
    body_style = ParagraphStyle(
        "Body", parent=styles["Normal"],
        fontSize=10, spaceAfter=4, leading=14,
    )
    muted_style = ParagraphStyle(
        "Muted", parent=body_style,
        textColor=colors.HexColor("#555555"),
    )

    TABLE_HEADER_BG = colors.HexColor("#f0ede8")
    TABLE_BORDER    = colors.HexColor("#e0ddd8")
    ACCENT          = colors.HexColor("#8b6914")

    story = []

    # ── Cover ──
    story.append(Spacer(1, 1 * cm))
    story.append(Paragraph("GEO Brand Citation Index", title_style))
    story.append(Paragraph(run_month_name, h2_style))
    story.append(Paragraph(
        f"Published by The GEO Lab · thegeolab.net · {run_month_name}",
        muted_style,
    ))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(
        "Which brands do AI platforms recommend — and why does it differ by platform?",
        body_style,
    ))
    story.append(Spacer(1, 1 * cm))

    # ── Summary table ──
    story.append(Paragraph("Top Brands — Overall", h2_style))

    top_rows = (
        db.query(CitationIndex)
        .filter_by(run_id=run.id, platform_slug="all", vertical_slug=None)
        .order_by(CitationIndex.rank)
        .limit(10)
        .all()
    )

    if top_rows:
        data = [["#", "Brand", "Archetype", "ChatGPT", "Perplexity", "Delta"]]
        for r in top_rows:
            delta = r.perplexity_vs_chatgpt_delta
            delta_str = f"{delta:+.0f}" if delta is not None else "—"
            data.append([
                str(r.rank),
                r.entity_name,
                r.archetype_label_public or "—",
                f"{r.chatgpt_score:.0f}" if r.chatgpt_score is not None else "—",
                f"{r.perplexity_score:.0f}" if r.perplexity_score is not None else "—",
                delta_str,
            ])

        col_widths = [1 * cm, 4.5 * cm, 5.5 * cm, 2 * cm, 2 * cm, 2 * cm]
        t = Table(data, colWidths=col_widths)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, TABLE_BORDER),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafaf8")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.5 * cm))

    # ── Archetype legend ──
    story.append(Paragraph("Archetype Definitions", h2_style))
    for slug, label in ARCHETYPE_PUBLIC_LABELS.items():
        if slug == "unclassified":
            continue
        descriptions = {
            "consensus_dominant": "High scores across all platforms. Low variance.",
            "training_dependent": "ChatGPT high, Perplexity significantly lower. Living on model memory.",
            "retrieval_driven": "Perplexity high, ChatGPT lower. Strong live web presence.",
            "ghost": "Moderate ChatGPT, near-zero Perplexity. Fading from live relevance.",
            "consensus_geo": "Consistently cited beyond what domain authority predicts.",
        }
        story.append(Paragraph(
            f"<b>{label}</b> — {descriptions.get(slug, '')}",
            body_style,
        ))
    story.append(Spacer(1, 0.5 * cm))

    # ── Per-vertical tables ──
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
            .limit(10)
            .all()
        )
        if not v_rows:
            continue

        story.append(PageBreak())
        story.append(Paragraph(f"Vertical: {vslug.replace('-', ' ').title()}", h2_style))
        data = [["#", "Brand", "Archetype", "ChatGPT", "Perplexity", "Delta"]]
        for r in v_rows:
            delta = r.perplexity_vs_chatgpt_delta
            delta_str = f"{delta:+.0f}" if delta is not None else "—"
            data.append([
                str(r.rank), r.entity_name,
                r.archetype_label_public or "—",
                f"{r.chatgpt_score:.0f}" if r.chatgpt_score is not None else "—",
                f"{r.perplexity_score:.0f}" if r.perplexity_score is not None else "—",
                delta_str,
            ])
        col_widths = [1 * cm, 4.5 * cm, 5.5 * cm, 2 * cm, 2 * cm, 2 * cm]
        t = Table(data, colWidths=col_widths)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, TABLE_BORDER),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafaf8")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.3 * cm))

    # ── Footer ──
    story.append(PageBreak())
    story.append(Paragraph("Methodology", h2_style))
    story.append(Paragraph(
        "25 queries run monthly across ChatGPT, Perplexity, and Gemini. "
        "Brands scored by position-weighted citation frequency, normalised within vertical. "
        "Archetypes classified by cross-platform delta analysis.",
        body_style,
    ))
    story.append(Paragraph(
        "Full methodology: thegeolab.net/geo-brand-citation-index/methodology/",
        muted_style,
    ))

    doc.build(story)
    log.info(f"PDF report saved: {out_path}")
    return out_path
