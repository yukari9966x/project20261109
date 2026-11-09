#!/usr/bin/env python3
"""합성 표준안 생성기.

가상 표준 "KS X 9999:2026 디지털 체중계 — 제1부: 일반 요구사항"을 KSDT 유사 스타일로 만든다.
실제 KS 문서의 내용은 쓰지 않는다(정형문 제외).

- samples/sample_01_violations.docx : P0·P0b 규칙 위반 주입본 (+ _expected.json, _roles.json)
- samples/sample_02_clean.docx      : 올바른 판(오탐 측정용) (+ _roles.json)
- samples/sample_03_messy_styles.docx : 스타일 없음·직접 서식·손번호(HWP 변환본 유사) (+ _roles.json)
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import struct
import sys
import zipfile
import zlib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from docx import Document  # noqa: E402
from docx.enum.section import WD_SECTION  # noqa: E402
from docx.enum.style import WD_STYLE_TYPE  # noqa: E402
from docx.enum.table import WD_TABLE_ALIGNMENT  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
from docx.oxml import OxmlElement, parse_xml  # noqa: E402
from docx.oxml.ns import nsdecls, qn  # noqa: E402
from docx.shared import Mm, Pt, RGBColor  # noqa: E402

from ksfix.assets import boilerplate  # noqa: E402
from ksfix.model.builder import build_from_document  # noqa: E402

FIXED_ZIP_TIME = (2026, 11, 9, 0, 0, 0)
FIXED_DT = dt.datetime(2026, 11, 9, 0, 0, 0)
STD = "KS X 9999:2026"
TITLE_KO = "디지털 체중계 — 제1부: 일반 요구사항"
TITLE_EN = "Digital body weight scales — Part 1: General requirements"

# 번호 정의 ID(기본 템플릿과 겹치지 않게 큰 값)
ABS_HEADING, NUM_HEADING, NUM_HEADING_JUMP = 101, 101, 109
ABS_ANNEX, NUM_ANNEX = 102, 102
ABS_LIST, NUM_LIST = 103, 103
ABS_NOTE, NUM_NOTE = 104, 104
ABS_SEQ = 105

# 스타일: (스타일 ID, 이름) — ID는 일부러 이름과 무관한 ASCII로 둔다(실제 KSDT 문서처럼).
KSDT_STYLES = {
    "doc_title": ("KSDT1", "[KSDT] 문서 제목"),
    "foreword_title": ("KSDT2", "[KSDT] 머리말 제목"),
    "std_number": ("KSDT3", "[KSDT] 본문 규격번호"),
    "ks_label": ("KSDT4", "[KSDT] 본문 한국산업규격"),
    "title_ko": ("KSDT5", "[KSDT] 본문 규격서 제목 한글"),
    "title_en": ("KSDT6", "[KSDT] 본문 규격서 제목 영어"),
    "table_title": ("KSDT7", "[KSDT] 표제목"),
    "figure_title": ("KSDT8", "[KSDT] 그림제목"),
    "annex": ("KSDT9", "[KSDT] 부속서 A"),
    "annex_1": ("KSDTa", "[KSDT] A.1"),
    "annex_title": ("KSDTb", "[KSDT] 부속서 제목"),
    "cover_number": ("KSDTc", "[KSDT] 표지 상단 규격번호"),
    "cover_title": ("KSDTd", "[KSDT] 표지 규격서 제목"),
    "cover_info": ("KSDTe", "[KSDT] 표지 기사란 내용"),
    "back_number": ("KSDTf", "[KSDT] 뒷표지 규격번호"),
    "back_title": ("KSDTg", "[KSDT] 뒷표지 영문 규격제목"),
    "list_a": ("a0", "번호매기기 a)"),
    "note": ("15", "비고1"),
    "toc1": ("TOC1", "toc 1"),
    "toc2": ("TOC2", "toc 2"),
}


# ── 보조: PNG(표준 라이브러리만) ──────────────────────────────
def make_png(width: int = 240, height: int = 140) -> bytes:
    """체중계 모양의 단순한 회색조 PNG."""
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            c = 255
            if x in (0, width - 1) or y in (0, height - 1):
                c = 0
            elif 20 <= x < width - 20 and 70 <= y < 120:
                edge = x in (20, width - 21) or y in (70, 119)
                c = 0 if edge else 205
            elif 90 <= x < 150 and 25 <= y < 50:
                edge = x in (90, 149) or y in (25, 49)
                c = 0 if edge else 235
            row += bytes((c, c, c))
        rows.append(bytes(row))

    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
        + chunk(b"IEND", b"")
    )


def deterministic_zip(data: bytes) -> bytes:
    """zip 항목 시각을 고정해 같은 입력이면 같은 내용이 나오게 한다."""
    src = zipfile.ZipFile(io.BytesIO(data))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            zi = zipfile.ZipInfo(info.filename, FIXED_ZIP_TIME)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            dst.writestr(zi, src.read(info.filename))
    return out.getvalue()


# ── 스타일·번호 설정 ───────────────────────────────────────
def _numbering_el(doc: Any) -> Any:
    return doc.part.numbering_part.element


def add_abstract(doc: Any, abs_id: int, levels: list[dict]) -> None:
    lv_xml = []
    for lv in levels:
        pst = f'<w:pStyle w:val="{lv["pstyle"]}"/>' if lv.get("pstyle") else ""
        lv_xml.append(
            f'<w:lvl w:ilvl="{lv["ilvl"]}"><w:start w:val="{lv.get("start", 1)}"/>'
            f'<w:numFmt w:val="{lv["fmt"]}"/>{pst}<w:lvlText w:val="{lv["text"]}"/>'
            f'<w:lvlJc w:val="left"/></w:lvl>'
        )
    el = parse_xml(
        f'<w:abstractNum {nsdecls("w")} w:abstractNumId="{abs_id}">'
        f'<w:multiLevelType w:val="multilevel"/>{"".join(lv_xml)}</w:abstractNum>'
    )
    numbering = _numbering_el(doc)
    first_num = numbering.find(qn("w:num"))
    if first_num is not None:
        first_num.addprevious(el)
    else:
        numbering.append(el)


def add_num(
    doc: Any, num_id: int, abs_id: int, start_overrides: dict[int, int] | None = None
) -> None:
    ovs = "".join(
        f'<w:lvlOverride w:ilvl="{il}"><w:startOverride w:val="{st}"/></w:lvlOverride>'
        for il, st in (start_overrides or {}).items()
    )
    _numbering_el(doc).append(
        parse_xml(
            f'<w:num {nsdecls("w")} w:numId="{num_id}"><w:abstractNumId w:val="{abs_id}"/>{ovs}</w:num>'
        )
    )


def set_style_numpr(style: Any, num_id: int | None = None, ilvl: int | None = None) -> None:
    ppr = style.element.get_or_add_pPr()
    numpr = ppr.get_or_add_numPr()
    if ilvl is not None:
        numpr.get_or_add_ilvl().val = ilvl
    if num_id is not None:
        numpr.get_or_add_numId().val = num_id


def add_pstyle(
    doc: Any,
    key: str,
    *,
    base: str = "Normal",
    center: bool = False,
    right: bool = False,
    bold: bool = False,
    size: float | None = None,
) -> Any:
    sid, name = KSDT_STYLES[key]
    style = doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
    style.style_id = sid
    style.base_style = doc.styles[base]
    if center:
        style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if right:
        style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    if bold:
        style.font.bold = True
    if size:
        style.font.size = Pt(size)
    return style


def setup_ksdt(doc: Any) -> dict[str, Any]:
    """KSDT 유사 스타일과 다단계 번호를 만든다."""
    normal = doc.styles["Normal"]
    normal.font.size = Pt(10)
    normal.paragraph_format.space_after = Pt(4)

    add_abstract(
        doc,
        ABS_HEADING,
        [
            {
                "ilvl": i,
                "fmt": "decimal",
                "text": ".".join(f"%{k + 1}" for k in range(i + 1)),
                "pstyle": f"Heading{i + 1}",
            }
            for i in range(6)
        ],
    )
    add_num(doc, NUM_HEADING, ABS_HEADING)
    add_num(doc, NUM_HEADING_JUMP, ABS_HEADING, {0: 8})  # 위반 주입용(번호 건너뜀)

    styles: dict[str, Any] = {}
    for i in range(1, 7):
        st = doc.styles[f"Heading {i}"]
        st.font.color.rgb = RGBColor(0, 0, 0)
        st.font.size = Pt(12 if i == 1 else 10.5)
        st.font.bold = True
        if i == 1:
            set_style_numpr(st, num_id=NUM_HEADING)
        else:
            # 실제 KSDT처럼 Heading 2 이하는 상위 제목에서 numId를 물려받고 ilvl만 지정
            st.base_style = doc.styles["Heading 1"]
            set_style_numpr(st, ilvl=i - 1)
        styles[f"h{i}"] = st

    styles["doc_title"] = add_pstyle(doc, "doc_title", center=True, bold=True, size=16)
    styles["foreword_title"] = add_pstyle(doc, "foreword_title", center=True, bold=True, size=14)
    styles["std_number"] = add_pstyle(doc, "std_number", right=True, bold=True, size=12)
    styles["ks_label"] = add_pstyle(doc, "ks_label", right=True, size=10)
    styles["title_ko"] = add_pstyle(doc, "title_ko", center=True, bold=True, size=20)
    styles["title_en"] = add_pstyle(doc, "title_en", center=True, size=12)
    styles["table_title"] = add_pstyle(doc, "table_title", center=True, bold=True)
    styles["figure_title"] = add_pstyle(doc, "figure_title", center=True, bold=True)
    styles["annex_title"] = add_pstyle(doc, "annex_title", center=True, bold=True, size=12)
    styles["cover_number"] = add_pstyle(doc, "cover_number", right=True, bold=True, size=14)
    styles["cover_title"] = add_pstyle(doc, "cover_title", center=True, bold=True, size=22)
    styles["cover_info"] = add_pstyle(doc, "cover_info")
    styles["back_number"] = add_pstyle(doc, "back_number", center=True, bold=True, size=14)
    styles["back_title"] = add_pstyle(doc, "back_title", center=True, size=12)
    styles["toc1"] = add_pstyle(doc, "toc1")
    styles["toc2"] = add_pstyle(doc, "toc2")

    annex_sid = KSDT_STYLES["annex"][0]
    annex1_sid = KSDT_STYLES["annex_1"][0]
    add_abstract(
        doc,
        ABS_ANNEX,
        [
            {"ilvl": 0, "fmt": "upperLetter", "text": "부속서 %1", "pstyle": annex_sid},
            {"ilvl": 1, "fmt": "decimal", "text": "%1.%2", "pstyle": annex1_sid},
        ],
    )
    add_num(doc, NUM_ANNEX, ABS_ANNEX)
    styles["annex"] = add_pstyle(doc, "annex", center=True, bold=True, size=14)
    set_style_numpr(styles["annex"], num_id=NUM_ANNEX)  # ilvl은 lvl/pStyle 연결로 결정
    styles["annex_1"] = add_pstyle(doc, "annex_1", base="Heading 2", bold=True)
    set_style_numpr(styles["annex_1"], num_id=NUM_ANNEX)

    list_sid = KSDT_STYLES["list_a"][0]
    add_abstract(
        doc, ABS_LIST, [{"ilvl": 0, "fmt": "lowerLetter", "text": "%1)", "pstyle": list_sid}]
    )
    add_num(doc, NUM_LIST, ABS_LIST)
    styles["list_a"] = add_pstyle(doc, "list_a")
    set_style_numpr(styles["list_a"], num_id=NUM_LIST)

    note_sid = KSDT_STYLES["note"][0]
    add_abstract(doc, ABS_NOTE, [{"ilvl": 0, "fmt": "decimal", "text": "비고", "pstyle": note_sid}])
    add_num(doc, NUM_NOTE, ABS_NOTE)
    styles["note"] = add_pstyle(doc, "note")
    set_style_numpr(styles["note"], num_id=NUM_NOTE)
    return styles


def setup_page(section: Any) -> None:
    section.page_width = Mm(210)
    section.page_height = Mm(297)
    section.top_margin = section.bottom_margin = Mm(28.5)
    section.left_margin = section.right_margin = Mm(22.5)


# ── 생성기 ─────────────────────────────────────────────────
class Gen:
    def __init__(self, variant: str):
        assert variant in ("clean", "violations", "messy")
        self.v = variant
        self.doc = Document()
        self.role_of: dict[Any, str] = {}
        self.expected: list[dict] = []
        self.ksdt = variant != "messy"
        self.st = setup_ksdt(self.doc) if self.ksdt else {}
        setup_page(self.doc.sections[0])
        self.h = [0] * 6  # 손번호용 카운터
        self.annex_letter = "@"
        self.png = make_png()

    @property
    def bad(self) -> bool:
        return self.v == "violations"

    # 기록
    def tag(self, paragraph: Any, role: str) -> Any:
        self.role_of[paragraph._p] = role
        return paragraph

    def expect(self, rule_id: str, where: str) -> None:
        self.expected.append({"rule_id": rule_id, "where": where})

    # 기본 문단
    def p(
        self,
        text: str = "",
        role: str = "body",
        style: Any = None,
        *,
        bold: bool | None = None,
        center: bool = False,
        right: bool = False,
        size: float | None = None,
    ) -> Any:
        para = (
            self.doc.add_paragraph(style=style) if style is not None else self.doc.add_paragraph()
        )
        if text:
            run = para.add_run(text)
            if bold is not None:
                run.bold = bold
            if size:
                run.font.size = Pt(size)
        if center:
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if right:
            para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        return self.tag(para, role if text else "empty")

    def empty(self) -> Any:
        return self.p("", "empty")

    def section_break(self) -> None:
        sec = self.doc.add_section(WD_SECTION.NEW_PAGE)
        setup_page(sec)

    # 제목
    def heading(self, level: int, title: str, *, num_id: int | None = None) -> Any:
        self.h[level - 1] += 1
        for k in range(level, 6):
            self.h[k] = 0
        number = ".".join(str(self.h[k]) for k in range(level))
        if self.ksdt:
            para = self.p(title, "heading", self.st[f"h{level}"])
            if num_id is not None:
                numpr = para._p.get_or_add_pPr().get_or_add_numPr()
                numpr.get_or_add_numId().val = num_id
        else:
            para = self.p(
                f"{number} {title}", "heading", bold=True, size=12 if level == 1 else 10.5
            )
        return para

    def annex_heading(self, status: str, title: str, typed_letter: str | None = None) -> Any:
        """KSDT: 한 문단에 '부속서 A'(자동번호) + 줄바꿈 + (규정) + 제목. messy: 세 문단."""
        if typed_letter is None:
            self.annex_letter = chr(ord(self.annex_letter) + 1)
            letter = self.annex_letter
        else:
            letter = typed_letter
        self.h = [0] * 6
        if self.ksdt and typed_letter is None:
            return self.p(f"\n({status})\n\n{title}", "annex_heading", self.st["annex"])
        if self.ksdt:
            return self.p(
                f"부속서 {letter}\n({status})\n\n{title}", "annex_heading", self.st["annex_title"]
            )
        self.p(f"부속서 {letter}", "annex_heading", bold=True, center=True, size=14)
        self.p(f"({status})", "annex_status", bold=True, center=True)
        return self.p(title, "annex_title", bold=True, center=True, size=12)

    def annex_clause(self, title: str, letter: str | None = None, typed: bool = False) -> Any:
        self.h[1] += 1
        letter = letter or self.annex_letter
        if self.ksdt and not typed:
            return self.p(title, "heading", self.st["annex_1"])
        return self.p(f"{letter}.{self.h[1]} {title}", "heading", bold=True)

    # 표·그림
    def caption_field(self, para: Any, prefix: str, seq: str, number: int, rest: str) -> None:
        para.add_run(prefix)
        self.field_runs(para, f"SEQ {seq} \\* ARABIC", str(number))
        para.add_run(rest)

    def field_runs(self, para: Any, instr: str, result: str) -> None:
        def fld(kind: str) -> None:
            r = para.add_run()
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), kind)
            r._r.append(el)

        fld("begin")
        r = para.add_run()
        it = OxmlElement("w:instrText")
        it.set(qn("xml:space"), "preserve")
        it.text = f" {instr} "
        r._r.append(it)
        fld("separate")
        para.add_run(result)
        fld("end")

    def table(self, rows: list[list[str]], *, header: bool = True) -> Any:
        t = self.doc.add_table(rows=len(rows), cols=len(rows[0]))
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for r_i, row in enumerate(rows):
            for c_i, val in enumerate(row):
                cell = t.cell(r_i, c_i)
                para = cell.paragraphs[0]
                run = para.add_run(val)
                if header and r_i == 0:
                    run.bold = True
                para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                if val:
                    self.tag(para, "table_cell")
        if header:
            tr_pr = t.rows[0]._tr.get_or_add_trPr()
            tr_pr.append(OxmlElement("w:tblHeader"))
        return t

    def figure(self) -> Any:
        para = self.doc.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        para.add_run().add_picture(io.BytesIO(self.png), width=Mm(60))
        return self.tag(para, "figure")

    # TOC
    def toc_entries(self) -> list[tuple[int, str]]:
        return [
            (1, "머  리  말\tii"),
            (1, "개    요\tiii"),
            (1, "1\t적용범위\t1"),
            (1, "2\t인용표준\t1"),
            (1, "3\t용어와 정의\t1"),
            (1, "4\t일반 요구사항\t2"),
            (2, "4.1\t구조\t2"),
            (2, "4.2\t표시 장치\t2"),
            (1, "5\t시험 방법\t3"),
            (2, "5.1\t시험 조건\t3"),
            (2, "5.2\t정확도 시험\t3"),
            (2, "5.3\t진동 시험\t4"),
            (1, "6\t표시\t4"),
            (2, "6.1\t표시 사항\t4"),
            (2, "6.2\t표시 방법\t4"),
            (1, "7\t포장\t4"),
            (1, "부속서 A (규정) 교정 절차\t5"),
            (1, "부속서 B (참고) 사용상의 주의\t6"),
            (1, "참고문헌\t7"),
            (1, f"{STD} 해  설\t8"),
        ]

    def toc(self) -> None:
        self.p("목    차", "toc_title", self.st["doc_title"])
        self.empty()
        entries = self.toc_entries()
        if self.bad:
            # 손으로 쓴 목차(TOC-01) + 실제 제목과 다른 항목(TOC-02)
            self.expect("TOC-01", "목차")
            for _, text in entries:
                if text.startswith("5\t시험 방법"):
                    text = "5\t시험\t3"
                    self.expect("TOC-02", "5\t시험\t3")
                self.p(text, "toc_entry")
            return
        last = len(entries) - 1
        for i, (level, text) in enumerate(entries):
            para = self.doc.add_paragraph(style=self.st[f"toc{level}"])
            if i == 0:
                self._fld_char(para, "begin")
                r = para.add_run()
                it = OxmlElement("w:instrText")
                it.set(qn("xml:space"), "preserve")
                it.text = ' TOC \\o "1-2" \\h \\z \\u '
                r._r.append(it)
                self._fld_char(para, "separate")
            para.add_run(text)
            if i == last:
                self._fld_char(para, "end")
            self.tag(para, "toc_entry")

    def _fld_char(self, para: Any, kind: str) -> None:
        r = para.add_run()
        el = OxmlElement("w:fldChar")
        el.set(qn("w:fldCharType"), kind)
        r._r.append(el)


# ── 내용 ───────────────────────────────────────────────────
def write_cover(g: Gen) -> None:
    g.p("KS", "cover", g.st["cover_number"])
    g.p(STD, "cover", g.st["cover_number"])
    g.empty()
    g.p(TITLE_KO, "cover", g.st["cover_title"])
    g.p(TITLE_EN, "cover", g.st["cover_title"])
    g.empty()
    g.p("2026년 11월 9일 제정", "cover", g.st["cover_info"])
    g.p("산업통상자원부 국가기술표준원", "cover", g.st["cover_info"])
    g.section_break()
    g.p("심    의 : 산업표준심의회 계량측정 기술심의회", "cover_info", g.st["cover_info"])
    g.p("원안작성협력 : ○○ 표준개발협력기관", "cover_info", g.st["cover_info"])
    g.p("표준열람 : e나라표준인증(http://www.standard.go.kr)", "cover_info", g.st["cover_info"])
    g.p("제    정 : 2026년 11월 9일", "cover_info", g.st["cover_info"])
    g.section_break()


def write_front(g: Gen) -> None:
    bp = boilerplate()
    title_style = g.st.get("foreword_title")

    def title(text: str, role: str) -> None:
        if g.ksdt:
            g.p(text, role, title_style)
        else:
            g.p(text, role, bold=True, center=True, size=14)

    def foreword() -> None:
        title("머  리  말", "foreword_title")
        g.p(bp["foreword"]["issue"]["enact"], "foreword")
        g.p(bp["foreword"]["copyright"][0], "foreword")
        if g.bad:
            g.expect("BLT-02", "머리말")  # 저작권 정형문 둘째 문장 누락
        else:
            g.p(bp["foreword"]["copyright"][1], "foreword")
        g.p(bp["foreword"]["patent"][0], "foreword")
        g.empty()

    def intro() -> None:
        title("개    요", "intro_title")
        g.p(
            "디지털 체중계는 가정과 체육 시설 등에서 널리 쓰이고 있으나, 제품마다 정확도와 표시 방법이 "
            "달라 소비자가 측정값을 비교하기 어렵다.",
            "intro",
        )
        g.p(
            "이 표준은 디지털 체중계의 정확도, 안전성 및 표시에 관한 공통 요구사항을 정하여 제품 간 비교 "
            "가능성을 높이기 위해 개발되었다.",
            "intro",
        )
        if g.bad:
            g.p("체중계는 KS X 9999-2에 따라 시험하여야 한다.", "intro")
            g.expect("STR-04", "KS X 9999-2에 따라 시험하여야 한다")
        g.empty()

    if g.bad:
        intro()  # 요소 순서 위반(STR-02): 개요가 머리말보다 앞
        foreword()
        g.expect("STR-02", "머리말")
    else:
        foreword()
        intro()


def write_title_block(g: Gen) -> None:
    std = "KS X 9999 : 2026" if g.bad else STD
    title_ko = TITLE_KO.replace(" — ", " - ") if g.bad else TITLE_KO
    if g.ksdt:
        g.p("한국산업표준", "std_number", g.st["ks_label"])
        g.p(std, "std_number", g.st["std_number"])
        g.p(title_ko, "title_ko", g.st["title_ko"])
        if not g.bad:
            g.p(TITLE_EN, "title_en", g.st["title_en"])
    else:
        g.p("한국산업표준", "std_number", right=True)
        g.p(std, "std_number", bold=True, right=True, size=12)
        g.p(title_ko, "title_ko", bold=True, center=True, size=20)
        g.p(TITLE_EN, "title_en", center=True, size=12)
    if g.bad:
        g.expect("TTL-04", "KS X 9999 : 2026")
        g.expect("TTL-01", "디지털 체중계 - 제1부")
        g.expect("STR-01", "디지털 체중계")  # 영문 제목 누락
    g.empty()


def write_scope_normref_terms(g: Gen) -> None:
    bp = boilerplate()
    g.heading(1, "적용범위")
    g.p(
        "이 표준은 가정용 및 업무용 디지털 체중계(이하 체중계라 한다)의 일반 요구사항, 시험 방법 및 "
        "표시에 대하여 규정한다."
    )
    g.p("이 표준은 의료기기로 허가된 체성분 분석기에는 적용되지 않는다.")
    if g.bad:
        g.p("체중계는 이 표준에 적합하여야 한다.")
        g.expect("STR-04", "이 표준에 적합하여야 한다")

    g.heading(1, "인용표준")
    intro = bp["normref"]["intro"]
    if g.bad:
        intro = intro.replace("필수적이다", "필요하다")
        g.expect("BLT-03", "다음의 인용표준은")
    g.p(intro, "normref_intro")
    entries = [
        "KS A 0006, 시험 장소의 표준 상태",
        "KS C IEC 60068-2-6, 환경 시험 — 제2-6부: 시험 — 시험 Fc: 진동(정현파)",
        "IEC 61010-1:2010, Safety requirements for electrical equipment for measurement, "
        "control, and laboratory use — Part 1: General requirements",
    ]
    if g.bad:
        entries = [
            entries[2],
            entries[0],
            "KS C IEC 60068-2-6 : 2007, 환경 시험 — 제2-6부: 시험 — 시험 Fc: 진동(정현파)",
            "계량에 관한 법률",
        ]
        g.expect("NRF-01", "KS A 0006")
        g.expect("REF-04", "60068-2-6 : 2007")
        g.expect("NRF-03", "계량에 관한 법률")
    for e in entries:
        g.p(e, "normref_entry")

    g.heading(1, "용어와 정의")
    if g.bad:
        g.expect("BLT-04", "용어와 정의")
    else:
        g.p(bp["terms"]["intro1"], "terms_intro")
    terms = [
        ("최대 칭량(maximum capacity)", "체중계가 표시할 수 있는 최대 질량값", None),
        (
            "눈금 간격(scale interval)",
            "인접한 두 표시값 사이의 차이",
            "[출처: KS X 9999-2:2026, 3.4]",
        ),
        ("영점 조정(zero setting)", "하중이 없을 때 표시값을 0으로 맞추는 기능", None),
    ]
    for i, (term, definition, source) in enumerate(terms, start=1):
        if g.bad and i == 2:
            term = "눈금 간격 (scale interval)"
            definition += "."
            g.expect("TRM-01", "눈금 간격 (scale interval)")
            g.expect("TRM-02", "인접한 두 표시값 사이의 차이.")
        if g.ksdt:
            # 자동번호 Heading 2 + 줄바꿈 + 용어(실제 발간본 형식)
            g.h[1] += 1
            g.p(f"\n{term}", "term", g.st["h2"])
        else:
            g.p(f"3.{i}", "term_number", bold=True)
            g.p(term, "term", bold=True)
        g.p(definition, "definition")
        if source:
            g.p(source, "term_source")
    g.empty()


def write_clause4(g: Gen) -> None:
    g.heading(1, "일반 요구사항")
    if g.bad:
        g.p("이 절은 체중계의 일반 요구사항을 규정한다.")
        g.expect("STR-03", "이 절은 체중계의 일반 요구사항을 규정한다")
    g.heading(2, "구조")
    if g.bad:
        g.p("미끄럼 방지 패드는 40 mm x 40 mm 이상이어야 한다.")
        g.expect("QTY-06", "40 mm x 40 mm")
        g.p("받침판은 2,000 N의 하중에 견뎌야 한다.")
        g.expect("QTY-03", "2,000 N")
        g.p("체중계의 최대 칭량은 150kg 이상이어야 한다.")
        g.expect("QTY-01", "150kg")
        g.p("받침판의 면적은 900 cm2 이상이어야 한다.")
        g.expect("QTY-07", "900 cm2")
        # 그림 제목이 그림 위(FIG-02), 호칭 꼴 오류(FIG-01), 본문 참조 없음(FIG-03), 스타일 아님(FMT-01)
        g.p("그림1. 구조", "figure_caption", center=True)
        g.figure()
        for rid in ("FIG-01", "FIG-02", "FIG-03", "FMT-01"):
            g.expect(rid, "그림1. 구조")
    else:
        g.p("미끄럼 방지 패드는 40 mm × 40 mm 이상이어야 한다.")
        g.p("받침판은 2 000 N의 하중에 견뎌야 한다.")
        g.p("체중계의 최대 칭량은 150 kg 이상이어야 한다.")
        g.p("체중계의 각 부 명칭은 그림 1과 같다.")
        g.figure()
        if g.ksdt:
            cap = g.p("", "figure_caption", g.st["figure_title"])
            g.caption_field(cap, "그림 ", "그림", 1, " — 체중계의 구조")
            g.tag(cap, "figure_caption")
        else:
            g.p("그림 1 — 체중계의 구조", "figure_caption", bold=True, center=True)
    g.heading(2, "표시 장치")
    g.p("표시부의 글자 높이는 10 mm 이상이어야 한다.")
    if g.bad:
        g.p("눈금 간격은 .1 kg 이하이어야 한다.")
        g.expect("QTY-02", ".1 kg")
        g.p("전원은 건전지를 사용한다; 어댑터는 별매품이다.")
        g.expect("PUN-01", "건전지를 사용한다;")
        g.p("비고 1 표시부의 밝기는 주위 조도에 따라 자동으로 조절된다.", "note")
        g.expect("NTE-01", "비고 1 표시부의 밝기는")
    else:
        g.p("눈금 간격은 0.1 kg 이하이어야 한다.")
        if g.ksdt:
            g.p("표시부의 밝기는 주위 조도에 따라 자동으로 조절된다.", "note", g.st["note"])
        else:
            g.p("비고 표시부의 밝기는 주위 조도에 따라 자동으로 조절된다.", "note")
    g.empty()


def write_clause5(g: Gen) -> None:
    g.heading(1, "시험 방법")
    g.heading(2, "시험 조건")
    if g.bad:
        g.p("시험은 KS A 0006에 따른 표준 상태에서 온도 23 ± 2 ℃, 상대 습도 (50 ± 10) %로 한다.")
        g.expect("QTY-04", "23 ± 2 ℃")
    else:
        g.p("시험은 KS A 0006에 따른 표준 상태에서 온도 (23 ± 2) ℃, 상대 습도 (50 ± 10) %로 한다.")
    g.p("체중계는 시험 전에 시험 장소에 2 h 이상 두어야 한다.")
    if g.bad:
        g.p("비고 시험 장소에는 진동원이 없어야 한다.", "note")
        g.expect("STR-04", "시험 장소에는 진동원이 없어야 한다")
        g.p("5.2와 5.3의 시험은 순서를 바꿀 수 있다.")
        g.expect("VRB-02", "순서를 바꿀 수 있다")
        g.p("체중계는 「계량에 관한 법률」에 따른 형식승인을 받아야 한다.")
        g.expect("PUN-03", "「계량에 관한 법률」")

    g.heading(2, "정확도 시험")
    g.p("표 1에 따른 시험 하중을 받침판 중앙에 차례로 올려놓고 표시값을 읽는다.")
    rows = [["시험 하중", "허용 오차"], ["10", "± 0.1"], ["50", "± 0.2"], ["150", "± 0.3"]]
    if g.bad:
        g.table(rows)
        g.p("<표 1> 시험 하중과 허용 오차", "table_caption", center=True)
        for rid in ("TBL-01", "TBL-02", "FMT-01"):
            g.expect(rid, "<표 1>")
        g.p("측정 전에는 반드시 영점 조정을 하여야 한다.")
        g.expect("VRB-01", "반드시 영점 조정")
        g.p("각 시험 하중에서 표시값과 시험 하중의 차이는 표 1의 허용 오차 이내이어야 한다..")
        g.expect("PUN-06", "허용 오차 이내이어야 한다..")
        g.p("자세한 시험 조건은 표 5 참조.")
        g.expect("REF-01", "표 5 참조")
        g.p("측정 중에 체중계를 이동하면 안 된다.")
        g.expect("VRB-04", "이동하면 안 된다")
    else:
        if g.ksdt:
            cap = g.p("", "table_caption", g.st["table_title"])
            g.caption_field(cap, "표 ", "표", 1, " — 시험 하중과 허용 오차")
            g.tag(cap, "table_caption")
            g.p("단위: kg", "unit_label", right=True)
        else:
            g.p("표 1 — 시험 하중과 허용 오차", "table_caption", bold=True, center=True)
            g.p("단위: kg", "unit_label", right=True)
        g.table(rows)
        g.p("측정 전에는 영점 조정을 하여야 한다.")
        g.p("각 시험 하중에서 표시값과 시험 하중의 차이는 표 1의 허용 오차 이내이어야 한다.")

    g.heading(2, "진동 시험")
    if g.bad:
        # 6단계 세분(NUM-03). 각 단계에 항이 둘 이상이 되도록 구성
        g.heading(3, "시험 장치")
        g.heading(4, "진동대")
        g.heading(5, "고정 방법")
        g.heading(6, "볼트 고정")
        g.p("체중계는 볼트로 진동대에 고정한다.")
        g.expect("NUM-03", "5.3.1.1.1.1")
        g.heading(6, "클램프 고정")
        g.p("볼트 고정이 곤란하면 클램프로 고정한다.")
        g.heading(5, "고정 위치")
        g.p("고정 위치는 받침판의 네 모서리로 한다.")
        g.heading(4, "측정기")
        g.p("가속도계는 진동대 중앙에 설치한다.")
        g.heading(3, "시험 절차")
        g.p(
            "체중계는 KS C IEC 60068-2-6에 따라 10 Hz ∼ 55 Hz의 진동을 가한 후에도 5.2항의 "
            "요구사항을 만족하여야 한다."
        )
        g.expect("REF-02", "5.2항")
        g.p("시험 온도는 5 ~ 40 ℃로 한다.")
        g.expect("PUN-02", "5 ~ 40 ℃")
        g.expect("QTY-05", "5 ~ 40 ℃")
        g.p("정전기 방전 시험은 KS C IEC 61000-4-2에 따른다.")
        g.expect("NRF-02", "KS C IEC 61000-4-2")
    else:
        g.p(
            "체중계는 KS C IEC 60068-2-6에 따라 10 Hz ∼ 55 Hz의 진동을 가한 후에도 5.2의 "
            "요구사항을 만족하여야 한다."
        )
        g.p("시험 온도는 5 ℃ ∼ 40 ℃로 한다.")
        g.p("체중계는 최대 칭량의 1.5배 하중을 영구 변형 없이 견딜 수 있다.")
    g.empty()


def write_clause6_7(g: Gen) -> None:
    g.heading(1, "표시")
    g.heading(2, "표시 사항")
    g.p("체중계에는 다음 사항을 표시하여야 한다.")
    for item in ("제조자명 또는 상표", "모델명 및 제조 번호", "최대 칭량 및 눈금 간격"):
        if g.ksdt:
            g.p(item, "list_item", g.st["list_a"])
        else:
            letter = "abc"[
                ["제조자명 또는 상표", "모델명 및 제조 번호", "최대 칭량 및 눈금 간격"].index(item)
            ]
            g.p(f"{letter}) {item}", "list_item")
    if g.bad:
        # 6.2가 없어 6.1만 남음(NUM-02) + 번호 건너뛴 표(NUM-07) + 본문 참조 없는 표(TBL-04) + 표 안의 표(TBL-03)
        g.expect("NUM-02", "6.1 표시 사항")
        g.p("표시는 쉽게 지워지지 않는 방법으로 하여야 한다.")
        cap = g.p("표 3 — 표시 항목의 글자 크기", "table_caption", g.st["table_title"])
        g.tag(cap, "table_caption")
        g.expect("NUM-07", "표 3 — 표시 항목")
        g.expect("TBL-04", "표 3 — 표시 항목")
        t = g.table([["항목", "글자 높이"], ["제조자명", "3 mm 이상"], ["세부 항목", ""]])
        cell = t.cell(2, 1)
        inner = cell.add_table(rows=1, cols=2)
        for c_i, val in enumerate(("하위 칸 1", "하위 칸 2")):
            para = inner.cell(0, c_i).paragraphs[0]
            para.add_run(val)
            g.tag(para, "table_cell")
        g.expect("TBL-03", "하위 칸")
    else:
        g.heading(2, "표시 방법")
        g.p("표시는 쉽게 지워지지 않는 방법으로 하여야 한다.")
    if g.bad:
        g.heading(1, "포장", num_id=NUM_HEADING_JUMP)  # 7이 아닌 8로 번호가 매겨짐(NUM-01)
        g.expect("NUM-01", "8 포장")
    else:
        g.heading(1, "포장")
    g.p("체중계는 운송 중 충격으로 손상되지 않도록 포장하여야 한다.")
    g.empty()


def write_annexes(g: Gen) -> None:
    if g.bad:
        # 부속서 B → A 순서(NUM-06), 손으로 친 부속서 번호
        g.annex_heading("참고", "사용상의 주의", typed_letter="B")
        g.expect("NUM-06", "부속서 B")
        g.annex_clause("설치", letter="B", typed=True)
        g.p("체중계를 기울어진 바닥에 두면 측정값이 실제보다 작게 표시될 수 있다.")
        g.annex_heading("규정", "교정 절차", typed_letter="A")
        g.annex_clause("일반사항", letter="A", typed=True)
        g.p("교정은 표준 분동을 사용하여 한다.")
        g.annex_clause("교정 주기", letter="A", typed=True)
        g.p("교정은 1년마다 하는 것이 좋다.")
        return
    g.annex_heading("규정", "교정 절차")
    g.annex_clause("일반사항")
    g.p("교정은 표 A.1의 하중을 사용하여 한다.")
    if g.ksdt:
        g.p("표 A.1 — 교정 하중", "table_caption", g.st["table_title"])
    else:
        g.p("표 A.1 — 교정 하중", "table_caption", bold=True, center=True)
    g.p("단위: kg", "unit_label", right=True)
    g.table([["교정점", "하중"], ["1", "20"], ["2", "100"]])
    g.annex_clause("교정 주기")
    g.p("교정은 1년마다 하는 것이 좋다.")
    g.annex_heading("참고", "사용상의 주의")
    g.annex_clause("설치")
    g.p("체중계를 기울어진 바닥에 두면 측정값이 실제보다 작게 표시될 수 있다.")
    g.annex_clause("보관")
    g.p("체중계를 습한 곳에 오래 두면 내부 부품이 부식될 수 있다.")
    g.empty()


def write_biblio(g: Gen) -> None:
    if g.ksdt:
        g.p("참고문헌", "biblio_title", g.st["foreword_title"])
    else:
        g.p("참고문헌", "biblio_title", bold=True, center=True, size=14)
    g.p("[1]\tKS X 9999-2:2026, 디지털 체중계 — 제2부: 시험 방법", "biblio_entry")
    g.p(
        "[2]\tOIML R 76-1:2006, Non-automatic weighing instruments — Part 1: Metrological and "
        "technical requirements — Tests",
        "biblio_entry",
    )
    g.empty()


def write_commentary(g: Gen) -> None:
    bp = boilerplate()
    if g.ksdt:
        g.p(f"{STD}\n해  설", "commentary_title", g.st["foreword_title"])
    else:
        g.p("해  설", "commentary_title", bold=True, center=True, size=14)
    if g.bad:
        g.expect("BLT-06", "해설")
    else:
        g.p(bp["commentary"]["intro"], "commentary")
    g.p("1 제정의 취지", "commentary", bold=True)
    g.p("디지털 체중계의 정확도와 표시 방법을 통일하기 위하여 이 표준을 제정하였다.", "commentary")
    g.p("2 주요 내용", "commentary", bold=True)
    g.p("이 표준은 적용범위, 정확도 요구사항, 시험 방법 및 표시 방법을 규정한다.", "commentary")


def write_back_cover(g: Gen) -> None:
    g.section_break()
    g.p(STD, "back_cover", g.st["back_number"])
    g.p(TITLE_EN, "back_cover", g.st["back_title"])
    g.p("Korean Agency for Technology and Standards", "back_cover", g.st["back_title"])
    g.p("http://www.kats.go.kr", "back_cover", g.st["back_title"])


def generate(variant: str) -> tuple[bytes, list[str], list[dict]]:
    g = Gen(variant)
    if g.ksdt:
        write_cover(g)
        g.toc()
    write_front(g)
    if g.ksdt:
        g.section_break()
    write_title_block(g)
    write_scope_normref_terms(g)
    write_clause4(g)
    write_clause5(g)
    write_clause6_7(g)
    if g.bad:
        write_biblio(g)  # 부속서보다 앞에 온 참고문헌(STR-06)
        g.expect("STR-06", "참고문헌")
        write_annexes(g)
    else:
        write_annexes(g)
        write_biblio(g)
    write_commentary(g)
    if g.ksdt:
        write_back_cover(g)

    cp = g.doc.core_properties
    cp.author = "KS-Fix 합성 샘플 생성기"
    cp.title = f"{STD} {TITLE_KO} (합성 표준안)"
    cp.created = FIXED_DT
    cp.modified = FIXED_DT
    cp.last_modified_by = "KS-Fix"
    cp.revision = 1

    ksdoc = build_from_document(g.doc)
    roles: list[str] = []
    for para in ksdoc.paras:
        role = g.role_of.get(para.xml)
        if role is None:
            if para.text.strip():
                raise RuntimeError(f"역할이 지정되지 않은 문단: {para.idx} {para.text[:40]!r}")
            role = "empty"
        roles.append(role)
    buf = io.BytesIO()
    g.doc.save(buf)
    return deterministic_zip(buf.getvalue()), roles, g.expected


VARIANTS = {
    "sample_01_violations": "violations",
    "sample_02_clean": "clean",
    "sample_03_messy_styles": "messy",
}


def write_all(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for stem, variant in VARIANTS.items():
        data, roles, expected = generate(variant)
        path = out_dir / f"{stem}.docx"
        path.write_bytes(data)
        written.append(path)
        prefix = stem.split("_")[0] + "_" + stem.split("_")[1]
        (out_dir / f"{prefix}_roles.json").write_text(
            json.dumps(roles, ensure_ascii=False, indent=0) + "\n", encoding="utf-8"
        )
        if variant == "violations":
            (out_dir / f"{prefix}_expected.json").write_text(
                json.dumps(expected, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
            )
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="합성 표준안 생성기")
    ap.add_argument("-o", "--out", default=str(ROOT / "samples"), help="출력 디렉터리")
    args = ap.parse_args(argv)
    for path in write_all(Path(args.out)):
        print("생성:", path.relative_to(ROOT) if path.is_relative_to(ROOT) else path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
