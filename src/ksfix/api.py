"""KS-Fix 코어 API: bytes → 결과(네트워크·subprocess·전역 상태 없음)."""

from __future__ import annotations

from typing import Any

from ksfix.model import KSDoc, Para, Table
from ksfix.model.builder import build


def analyze(data: bytes) -> KSDoc:
    """docx bytes → 구조 인식까지 마친 KSDoc."""
    doc = build(data)
    try:
        from ksfix.classify import classify
    except ImportError:  # 구조 인식 모듈이 없을 때(개발 초기)
        return doc
    classify(doc)
    return doc


def _para_row(p: Para) -> dict[str, Any]:
    return {
        "idx": p.idx,
        "section": p.section_idx,
        "role": p.role.value,
        "conf": round(p.role_conf, 2),
        "style": p.style_name,
        "label": p.num_label,
        "level": p.attrs.get("level"),
        "clause": p.clause_no,
        "in_table": p.in_table,
        "text": p.text,
    }


def inspect_bytes(data: bytes) -> dict[str, Any]:
    doc = analyze(data)
    return {
        "meta": doc.meta,
        "blocks": [_para_row(p) for p in doc.paras],
        "tables": [
            {
                "idx": t.idx,
                "rows": len(t.cells),
                "cols": max((len(r) for r in t.cells), default=0),
                "nested": t.nested,
                "first_para": t.paras[0].idx if t.paras else None,
            }
            for t in doc.tables
            if isinstance(t, Table)
        ],
    }
