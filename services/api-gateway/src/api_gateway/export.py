"""Transcript export utilities — plain text and PDF generation."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from api_gateway.db import SessionModel, TranscriptSegment


def _format_ts(iso: str) -> str:
    """Convert ISO 8601 timestamp to HH:MM:SS for display."""
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%H:%M:%S")
    except Exception:
        return iso


def generate_txt(
    session: SessionModel,
    segments: list[TranscriptSegment],
) -> str:
    """Render a transcript as plain text."""
    lines: list[str] = []
    lines.append(f"Session: {session.label or session.id}")
    lines.append(f"Started: {session.started_at}")
    if session.stopped_at:
        lines.append(f"Stopped: {session.stopped_at}")
    lines.append("")

    for seg in segments:
        ts = _format_ts(seg.timestamp)
        speaker = seg.speaker or "Unknown"
        lines.append(f"[{ts}] {speaker}: {seg.text}")

    return "\n".join(lines) + "\n"


def generate_pdf(
    session: SessionModel,
    segments: list[TranscriptSegment],
) -> bytes:
    """Render a transcript as a PDF document."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 16)
    title = session.label or session.id
    pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")

    # Metadata
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(100, 100, 100)
    meta = f"Started: {session.started_at}"
    if session.stopped_at:
        meta += f"  |  Stopped: {session.stopped_at}"
    pdf.cell(0, 6, meta, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Transcript body
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 11)

    for seg in segments:
        ts = _format_ts(seg.timestamp)
        speaker = seg.speaker or "Unknown"
        line = f"[{ts}] {speaker}: {seg.text}"
        pdf.multi_cell(0, 6, line)
        pdf.ln(1)

    return bytes(pdf.output())
