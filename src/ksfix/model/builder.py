"""docx → KSDoc 문서 모델."""

from __future__ import annotations

import re
from typing import Any

from docx.opc.constants import RELATIONSHIP_TYPE as RT

from ksfix.io.loader import open_docx
from ksfix.model.ir import KSDoc, Para, Table
from ksfix.model.ns import child, child_val, on_off, w
from ksfix.model.numbering import Numbering, NumberingState
from ksfix.model.styles import StyleSheet
from ksfix.model.text import FieldTracker, extract

HANGUL_RE = re.compile(r"[가-힣]")
LATIN_RE = re.compile(r"[A-Za-z]")
TRACK_TAGS = ("ins", "del", "moveFrom", "moveTo", "pPrChange", "rPrChange")


def part_by_reltype(document_part: Any, reltype: str) -> Any:
    """관계 유형으로 부품을 찾는다(없으면 None, 새로 만들지 않는다)."""
    for rel in document_part.rels.values():
        if rel.reltype == reltype and not rel.is_external:
            return rel.target_part
    return None


def _int(val: str | None) -> int | None:
    try:
        return int(val) if val is not None else None
    except ValueError:
        return None


class _Builder:
    def __init__(self, document: Any):
        self.document = document
        styles_part = part_by_reltype(document.part, RT.STYLES)
        numbering_part = part_by_reltype(document.part, RT.NUMBERING)
        self.styles = StyleSheet(styles_part.element if styles_part is not None else None)
        self.numbering = Numbering(
            numbering_part.element if numbering_part is not None else None, self.styles
        )
        self.numstate = NumberingState(self.numbering)
        self.tracker = FieldTracker()
        self.paras: list[Para] = []
        self.tables: list[Table] = []
        self.section = 0

    # ── 순회 ──────────────────────────────────────────────
    def walk(self, parent: Any, out: list[Any], ctx: tuple[int, int, int] | None) -> None:
        for el in parent:
            tag = el.tag
            if tag == w("p"):
                out.append(self.para(el, ctx))
            elif tag == w("tbl"):
                out.append(self.table(el, ctx))
            elif tag == w("sdt"):
                content = el.find(w("sdtContent"))
                if content is not None:
                    self.walk(content, out, ctx)
            elif tag == w("customXml"):
                self.walk(el, out, ctx)

    def _rows(self, tbl: Any) -> list[Any]:
        rows = []
        for el in tbl:
            if el.tag == w("tr"):
                rows.append(el)
            elif el.tag in (w("sdt"), w("customXml")):
                content = el.find(w("sdtContent")) if el.tag == w("sdt") else el
                if content is not None:
                    rows.extend(r for r in content if r.tag == w("tr"))
        return rows

    def _cells(self, tr: Any) -> list[Any]:
        cells = []
        for el in tr:
            if el.tag == w("tc"):
                cells.append(el)
            elif el.tag in (w("sdt"), w("customXml")):
                content = el.find(w("sdtContent")) if el.tag == w("sdt") else el
                if content is not None:
                    cells.extend(c for c in content if c.tag == w("tc"))
        return cells

    def table(self, tbl: Any, ctx: tuple[int, int, int] | None) -> Table:
        t = Table(
            idx=len(self.tables),
            xml=tbl,
            cells=[],
            nested=False,
            section_idx=self.section,
            in_table=ctx is not None,
        )
        self.tables.append(t)
        if ctx is not None:
            self.tables[ctx[0]].nested = True
        for r_i, tr in enumerate(self._rows(tbl)):
            row: list[list[Para]] = []
            for c_i, tc in enumerate(self._cells(tr)):
                items: list[Any] = []
                self.walk(tc, items, (t.idx, r_i, c_i))
                row.append([b for b in items if isinstance(b, Para)])
            t.cells.append(row)
        return t

    def para(self, p: Any, ctx: tuple[int, int, int] | None) -> Para:
        ppr = p.find(w("pPr"))
        style_id = child_val(ppr, "pStyle") if ppr is not None else None
        eff_style = style_id or self.styles.default_para
        pt = extract(p, self.tracker)

        numpr = child(ppr, "numPr") if ppr is not None else None
        d_num = child_val(numpr, "numId") if numpr is not None else None
        d_ilvl = _int(child_val(numpr, "ilvl")) if numpr is not None else None
        s_num, s_ilvl = self.styles.resolve_numpr(eff_style)
        num_id = d_num if d_num is not None else s_num
        if d_ilvl is not None:
            ilvl: int | None = d_ilvl
        else:
            link = self.numbering.level_for_style(num_id, eff_style)
            ilvl = link if link is not None else (s_ilvl if s_ilvl is not None else 0)
        label = None
        if num_id and num_id != "0":
            label = self.numstate.next_label(num_id, ilvl)
        else:
            num_id, ilvl = None, None

        jc = child_val(ppr, "jc") if ppr is not None else None
        if jc is None:
            jc = self.styles.resolve(eff_style, "jc")
        outline = _int(child_val(ppr, "outlineLvl")) if ppr is not None else None
        if outline is None:
            outline = self.styles.resolve(eff_style, "outline_lvl")

        text_runs = {id(s.run): s.run for s in pt.spans if s.kind == "t" and s.end > s.start}
        style_bold = bool(self.styles.resolve(eff_style, "bold"))
        bolds: list[bool] = []
        sizes: list[int] = []
        for run in text_runs.values():
            rpr = run.find(w("rPr")) if hasattr(run, "find") else None
            b = on_off(rpr.find(w("b"))) if rpr is not None else None
            bolds.append(style_bold if b is None else b)
            sz = _int(child_val(rpr, "sz")) if rpr is not None else None
            if sz:
                sizes.append(sz)
        style_size = self.styles.resolve(eff_style, "size_half_pt")

        para = Para(
            idx=len(self.paras),
            xml=p,
            text=pt.text,
            spans=pt.spans,
            style_id=eff_style,
            style_name=self.styles.name(eff_style),
            num_label=label,
            num_level=ilvl,
            num_id=num_id,
            section_idx=self.section,
            in_table=ctx is not None,
            table_idx=ctx[0] if ctx else None,
            cell=(ctx[1], ctx[2]) if ctx else None,
            has_drawing=pt.has_drawing,
            has_field=pt.has_field,
            has_math=pt.has_math,
        )
        para.attrs.update(
            {
                "jc": jc,
                "outline": outline,
                "bold": all(bolds) if bolds else style_bold,
                "size": max(sizes) if sizes else style_size,
                "in_toc": pt.in_toc,
                "fields": pt.fields,
                "has_ins_del": pt.has_ins_del,
                "style_chain": self.styles.chain_names(eff_style),
                "heading_level": self.styles.heading_level(eff_style),
                "page_break_before": bool(
                    ppr is not None and on_off(child(ppr, "pageBreakBefore"))
                ),
            }
        )
        self.paras.append(para)
        if ppr is not None and child(ppr, "sectPr") is not None:
            self.section += 1
        return para


def build_from_document(document: Any, sha: str | None = None) -> KSDoc:
    b = _Builder(document)
    body = document.element.body
    blocks: list[Any] = []
    b.walk(body, blocks, None)

    all_text = "\n".join(p.text for p in b.paras)
    n_hangul = len(HANGUL_RE.findall(all_text))
    n_latin = len(LATIN_RE.findall(all_text))
    letters = n_hangul + n_latin
    tracked = any(body.find(f".//{w(t)}") is not None for t in TRACK_TAGS)
    comments_part = part_by_reltype(document.part, RT.COMMENTS)
    n_comments = 0
    if comments_part is not None:
        n_comments = len(comments_part.element.findall(w("comment")))
    settings_part = part_by_reltype(document.part, RT.SETTINGS)
    update_fields = False
    if settings_part is not None:
        uf = settings_part.element.find(w("updateFields"))
        update_fields = bool(on_off(uf)) if uf is not None else False

    meta = {
        "sha256": sha,
        "hangul_ratio": round(n_hangul / letters, 3) if letters else 0.0,
        "has_tracked_changes": tracked,
        "comment_count": n_comments,
        "sections": b.section + 1,
        "has_toc_field": any(p.attrs.get("in_toc") for p in b.paras),
        "update_fields": update_fields,
        "paragraph_count": len(b.paras),
        "table_count": len(b.tables),
    }
    return KSDoc(
        blocks=blocks,
        paras=b.paras,
        tables=b.tables,
        meta=meta,
        docx=document,
        styles=b.styles,
        numbering=b.numbering,
    )


def build(data: bytes) -> KSDoc:
    """docx bytes → KSDoc (입력 검증 포함)."""
    document, digest = open_docx(data)
    return build_from_document(document, digest)
