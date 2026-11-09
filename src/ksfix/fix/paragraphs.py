"""문단 삽입·삭제·이동(변경추적: 문단 표시와 런 모두 w:ins/w:del)."""

from __future__ import annotations

import copy
from typing import Any

from lxml import etree

from ksfix.fix.revisions import Revisions
from ksfix.fix.textedit import make_run
from ksfix.model.ns import w


def _ppr(p: Any) -> Any:
    ppr = p.find(w("pPr"))
    if ppr is None:
        ppr = etree.Element(w("pPr"))
        p.insert(0, ppr)
    return ppr


def _mark_paragraph(p: Any, tag: str, rev: Revisions) -> None:
    """문단 표시(¶)를 삽입/삭제로 표시: w:pPr/w:rPr/w:ins|w:del."""
    ppr = _ppr(p)
    rpr = ppr.find(w("rPr"))
    if rpr is None:
        rpr = etree.Element(w("rPr"))
        # rPr는 sectPr·pPrChange 앞에 와야 한다
        anchor = ppr.find(w("sectPr"))
        if anchor is None:
            anchor = ppr.find(w("pPrChange"))
        if anchor is not None:
            anchor.addprevious(rpr)
        else:
            ppr.append(rpr)
    rpr.insert(0, etree.Element(w(tag), rev.attrs()))


def new_paragraph(text: str, style_id: str | None, mode: str, rev: Revisions | None) -> Any:
    p = etree.Element(w("p"))
    if style_id:
        ppr = _ppr(p)
        ps = etree.SubElement(ppr, w("pStyle"))
        ps.set(w("val"), style_id)
    run = make_run(text, None)
    if mode == "tracked":
        _mark_paragraph(p, "ins", rev)
        ins = etree.SubElement(p, w("ins"), rev.attrs())
        ins.append(run)
    else:
        p.append(run)
    return p


def insert_paragraphs(
    anchor: Any,
    texts: list[str],
    where: str,
    style_id: str | None,
    mode: str,
    rev: Revisions | None,
) -> list[Any]:
    """anchor 문단 앞/뒤에 문단들을 순서대로 넣는다."""
    created = []
    ref = anchor
    for i, text in enumerate(texts):
        p = new_paragraph(text, style_id, mode, rev)
        if i == 0 and where == "before":
            anchor.addprevious(p)
        else:
            ref.addnext(p)
        ref = p
        created.append(p)
    return created


def _strip_sectpr(p: Any) -> None:
    ppr = p.find(w("pPr"))
    if ppr is not None:
        for sp in ppr.findall(w("sectPr")):
            ppr.remove(sp)


def delete_paragraph(p: Any, mode: str, rev: Revisions | None) -> None:
    if mode == "tracked":
        for child in list(p):
            if child.tag == w("r"):
                for t_el in child.findall(w("t")):
                    t_el.tag = w("delText")
                wrapper = etree.Element(w("del"), rev.attrs())
                child.addprevious(wrapper)
                wrapper.append(child)
        _mark_paragraph(p, "del", rev)
        return
    ppr = p.find(w("pPr"))
    if ppr is not None and ppr.find(w("sectPr")) is not None:
        for child in list(p):
            if child.tag != w("pPr"):
                p.remove(child)
        return
    p.getparent().remove(p)


def move_paragraph(p: Any, target: Any, where: str, mode: str, rev: Revisions | None) -> Any:
    """'삭제 + 삽입' 추적으로 문단을 옮긴다(추적 이동 대신 단순화). 반환: 새 위치의 문단."""
    clone = copy.deepcopy(p)
    _strip_sectpr(clone)
    if mode == "tracked":
        for child in list(clone):
            if child.tag == w("r"):
                wrapper = etree.Element(w("ins"), rev.attrs())
                child.addprevious(wrapper)
                wrapper.append(child)
        _mark_paragraph(clone, "ins", rev)
    if where == "before":
        target.addprevious(clone)
    else:
        target.addnext(clone)
    delete_paragraph(p, mode, rev)
    return clone
