"""Export helpers — CSV + PDF for the invoice decision trail."""

from __future__ import annotations

import io
from typing import Any

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def invoice_csv(rows: list[dict[str, Any]]) -> bytes:
    df = pd.DataFrame(rows)
    return df.to_csv(index=False).encode("utf-8")


def invoice_pdf(title: str, rows: list[dict[str, Any]]) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=LETTER, leftMargin=54, rightMargin=54, topMargin=54, bottomMargin=54
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph(title, styles["Title"]),
        Spacer(1, 12),
        Paragraph("Compass — Executive Acceptance Decision Trail", styles["Heading3"]),
        Spacer(1, 6),
        Paragraph("Zvolvant Solutions LLC", styles["Italic"]),
        Spacer(1, 12),
    ]
    if not rows:
        story.append(Paragraph("No decisions recorded yet.", styles["BodyText"]))
    else:
        df = pd.DataFrame(rows)
        cols = list(df.columns)
        data = [cols, *df.values.tolist()]
        t = Table(data, repeatRows=1, hAlign="LEFT")
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B2A4A")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F9FC")]),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E6EAF0")),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E6EAF0")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(t)
    doc.build(story)
    return buf.getvalue()
