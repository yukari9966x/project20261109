"""구조 인식: 역할 분류 + 문서 트리 + 메타데이터."""

from __future__ import annotations

import re

from ksfix.classify import patterns as pt
from ksfix.classify.heuristics import classify_roles
from ksfix.classify.tree import build_tree, compute_parts
from ksfix.model.ir import KSDoc, Role

LOW_CONFIDENCE = 0.6


def classify(doc: KSDoc) -> KSDoc:
    classify_roles(doc)
    doc.tree = build_tree(doc)
    doc.meta["parts"] = compute_parts(doc)
    std = next((p for p in doc.paras if p.role == Role.STD_NUMBER and "KS" in p.text), None)
    doc.meta["std_number"] = pt.clean(std.text) if std else None
    ko = [pt.clean(p.text) for p in doc.paras if p.role == Role.TITLE_KO]
    en = [pt.clean(p.text) for p in doc.paras if p.role == Role.TITLE_EN]
    doc.meta["title_ko"] = " ".join(ko) or None
    doc.meta["title_en"] = " ".join(en) or None
    adoption = None
    if doc.meta["std_number"] and re.search(r"\b(ISO|IEC)\b", doc.meta["std_number"]):
        adoption = "IDT"
    doc.meta["adoption"] = adoption
    doc.meta["ks_target"] = doc.meta.get("hangul_ratio", 0) >= 0.3
    doc.meta["low_confidence"] = sum(
        1 for p in doc.paras if p.role != Role.EMPTY and p.role_conf < LOW_CONFIDENCE
    )
    return doc


__all__ = ["LOW_CONFIDENCE", "classify"]
