"""문단 삽입·삭제·이동(변경추적: 문단 표시와 런 모두 w:ins/w:del)."""

from __future__ import annotations

import copy
from typing import Any

from lxml import etree

from ksfix.fix.revisions import AUTHOR, Revisions
from ksfix.fix.textedit import make_run
from ksfix.model.ns import w

SKIP_ANCESTORS = (w("txbxContent"),)


def _runs(p: Any, stop_tags: tuple[str, ...]) -> list[Any]:
    """문단 안 모든 깊이의 런 중 stop_tags 조상이 없는 것(텍스트 상자 안 런 제외)."""
    out = []
    for r in p.iter(w("r")):
        anc = r.getparent()
        skip = False
        while anc is not None and anc is not p:
            if anc.tag in stop_tags or anc.tag in SKIP_ANCESTORS:
                skip = True
                break
            anc = anc.getparent()
        if not skip:
            out.append(r)
    return out


def _nearest(el: Any, tag: str, stop: Any) -> Any:
    anc = el.getparent()
    while anc is not None and anc is not stop:
        if anc.tag == tag:
            return anc
        anc = anc.getparent()
    return None


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
        for r in _runs(p, (w("del"), w("moveFrom"))):
            ins = _nearest(r, w("ins"), p)
            if ins is not None and ins.get(w("author")) == AUTHOR:
                ins.remove(r)  # KS-Fix가 방금 넣은 텍스트는 삭제 표시 대신 없앤다
                continue
            for t_el in r.findall(w("t")):
                t_el.tag = w("delText")
            wrapper = etree.Element(w("del"), rev.attrs())
            r.addprevious(wrapper)
            wrapper.append(r)
        for ins in list(p.iter(w("ins"))):
            if ins.get(w("author")) == AUTHOR and len(ins) == 0 and ins.getparent() is not None:
                ins.getparent().remove(ins)
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
    if rev is not None:
        for tag in ("ins", "del", "pPrChange", "rPrChange", "moveFrom", "moveTo"):
            for el in clone.iter(w(tag)):
                if el.get(w("id")) is not None:
                    el.set(w("id"), str(rev.new_id()))
    if mode == "tracked":
        for r in _runs(clone, (w("ins"), w("del"), w("moveTo"), w("moveFrom"))):
            wrapper = etree.Element(w("ins"), rev.attrs())
            r.addprevious(wrapper)
            wrapper.append(r)
        _mark_paragraph(clone, "ins", rev)
    if where == "before":
        target.addprevious(clone)
    else:
        target.addnext(clone)
    delete_paragraph(p, mode, rev)
    return clone
