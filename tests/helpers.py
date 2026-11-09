"""테스트용 작은 docx 생성 도우미."""

from __future__ import annotations

import io
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH


def make_docx(items: list[Any]) -> bytes:
    """items: 문자열 또는 dict(text, bold, center, style, table=[[...]])."""
    doc = Document()
    for it in items:
        if isinstance(it, str):
            it = {"text": it}
        if "table" in it:
            rows = it["table"]
            t = doc.add_table(rows=len(rows), cols=len(rows[0]))
            for r, row in enumerate(rows):
                for c, val in enumerate(row):
                    t.cell(r, c).paragraphs[0].add_run(val)
            continue
        p = doc.add_paragraph(style=it.get("style"))
        run = p.add_run(it.get("text", ""))
        if it.get("bold"):
            run.bold = True
        if it.get("center"):
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def ks_skeleton(body: list[Any]) -> list[Any]:
    """머리말·제목·필수 절 골격 + 본문 항목."""
    return [
        {"text": "머  리  말", "bold": True, "center": True},
        "이 표준은 산업표준화법 관련 규정에 따라 산업표준심의회의 심의를 거쳐 제정한 한국산업표준이다.",
        {"text": "KS X 9998:2026", "bold": True},
        {"text": "시험용 장치 — 일반 요구사항", "bold": True, "center": True},
        {"text": "Test devices — General requirements", "center": True},
        {"text": "1 적용범위", "bold": True},
        "이 표준은 시험용 장치에 대하여 규정한다.",
        *body,
    ]
