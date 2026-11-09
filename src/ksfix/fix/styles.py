"""문단 서식 변경: 스타일·정렬(변경추적은 w:pPrChange에 이전 속성 보관)."""

from __future__ import annotations

import copy
from typing import Any

from lxml import etree

from ksfix.fix.revisions import Revisions
from ksfix.model.ns import w

# pPr 자식 순서(스키마). 새 요소를 알맞은 자리에 넣을 때 쓴다.
PPR_ORDER = [
    "pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr", "widowControl", "numPr",
    "suppressLineNumbers", "pBdr", "shd", "tabs", "suppressAutoHyphens", "kinsoku", "wordWrap",
    "overflowPunct", "topLinePunct", "autoSpaceDE", "autoSpaceDN", "bidi", "adjustRightInd",
    "snapToGrid", "spacing", "ind", "contextualSpacing", "mirrorIndents", "suppressOverlap", "jc",
    "textDirection", "textAlignment", "textboxTightWrap", "outlineLvl", "divId", "cnfStyle",
    "rPr", "sectPr", "pPrChange",
]  # fmt: skip


def _ppr(p: Any) -> Any:
    ppr = p.find(w("pPr"))
    if ppr is None:
        ppr = etree.Element(w("pPr"))
        p.insert(0, ppr)
    return ppr


def _set_child(ppr: Any, name: str, val: str | None) -> None:
    old = ppr.find(w(name))
    if val is None:
        if old is not None:
            ppr.remove(old)
        return
    if old is None:
        old = etree.Element(w(name))
        idx = PPR_ORDER.index(name)
        for later in PPR_ORDER[idx + 1 :]:
            anchor = ppr.find(w(later))
            if anchor is not None:
                anchor.addprevious(old)
                break
        else:
            ppr.append(old)
    old.set(w("val"), val)


def _record_change(ppr: Any, rev: Revisions) -> None:
    if ppr.find(w("pPrChange")) is not None:
        return  # 이미 KS-Fix 또는 다른 변경이 기록됨 → 처음 상태를 보존
    snapshot = etree.Element(w("pPr"))
    for child in ppr:
        if child.tag in (w("rPr"), w("sectPr"), w("pPrChange")):
            continue
        snapshot.append(copy.deepcopy(child))
    change = etree.SubElement(ppr, w("pPrChange"), rev.attrs())
    change.append(snapshot)


def set_style(p: Any, style_id: str, mode: str, rev: Revisions | None) -> None:
    ppr = _ppr(p)
    if mode == "tracked":
        _record_change(ppr, rev)
    _set_child(ppr, "pStyle", style_id)


def set_alignment(p: Any, jc: str, mode: str, rev: Revisions | None) -> None:
    ppr = _ppr(p)
    if mode == "tracked":
        _record_change(ppr, rev)
    _set_child(ppr, "jc", jc)
