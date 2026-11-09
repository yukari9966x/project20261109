"""구조 인식(역할 분류): 1차 문단 단위 신호 점수 → 2차 구역 상태 기계."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

from ksfix.assets import boilerplate
from ksfix.classify import patterns as pt
from ksfix.model.ir import OBJ, KSDoc, Para, Role

FRONT_TITLES = {Role.TOC_TITLE, Role.FOREWORD_TITLE, Role.INTRO_TITLE}
ZONE_OF_TITLE = {
    Role.TOC_TITLE: "toc",
    Role.FOREWORD_TITLE: "foreword",
    Role.INTRO_TITLE: "intro",
    Role.BIBLIO_TITLE: "biblio",
    Role.COMMENTARY_TITLE: "commentary",
}


@dataclass
class Cand:
    role: Role
    conf: float
    attrs: dict = field(default_factory=dict)


def _style_has(p: Para, *needles: str) -> bool:
    chain = p.attrs.get("style_chain") or []
    return any(any(n in name for n in needles) for name in chain)


def _style_name(p: Para) -> str:
    chain = p.attrs.get("style_chain") or []
    return chain[0] if chain else ""


def _numeric_label(label: str | None) -> bool:
    return bool(label) and bool(re.fullmatch(r"\d+(\.\d+)*", label or ""))


def _annex_clause_label(label: str | None) -> bool:
    return bool(label) and bool(re.fullmatch(r"[A-Z]\.\d+(\.\d+)*", label or ""))


def _title_role(sq: str) -> Role | None:
    if sq in ("목차", "차례"):
        return Role.TOC_TITLE
    if sq in ("표목차", "그림목차", "표및그림목차"):
        return Role.TOC_TITLE
    if sq == "머리말":
        return Role.FOREWORD_TITLE
    if sq == "개요":
        return Role.INTRO_TITLE
    if sq == "참고문헌":
        return Role.BIBLIO_TITLE
    if sq.endswith("해설") and len(sq) <= 40:
        return Role.COMMENTARY_TITLE
    return None


def parse_annex_heading(p: Para) -> dict:
    """'부속서 A' + '(규정)' + 제목을 한 문단에서 읽는다(KSDT 형식·손입력 모두)."""
    text = p.full_text
    m = re.search(r"부속서\s*(?P<letter>[A-Z]|\d+)", text)
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    status = None
    title_lines = []
    for ln in lines:
        sm = re.search(r"\(\s*(규정|참고)\s*\)", ln)
        if sm and status is None:
            status = sm.group(1)
            rest = ln[sm.end() :].strip()
            if rest:
                title_lines.append(rest)
            continue
        if re.match(r"^부속서\s*([A-Z]|\d+)\s*$", ln):
            continue
        ln2 = re.sub(r"^부속서\s*([A-Z]|\d+)\s*", "", ln)
        if ln2:
            title_lines.append(ln2)
    return {
        "letter": m.group("letter") if m else None,
        "status": status,
        "annex_title": " ".join(title_lines) or None,
    }


def local_candidate(p: Para) -> Cand | None:
    """문단 하나만 보고 내릴 수 있는 강한 판단."""
    text = p.text
    stripped = text.strip()
    sq = pt.squash(text)
    label = p.num_label
    sname = _style_name(p)

    if p.in_table:
        if not stripped and not p.has_drawing:
            return Cand(Role.EMPTY, 1.0)
        return Cand(Role.TABLE_CELL, 0.9)

    if p.attrs.get("in_toc") or re.fullmatch(r"toc \d|table of figures", sname or ""):
        if stripped:
            return Cand(Role.TOC_ENTRY, 0.95)

    if not stripped and not p.has_drawing and not label:
        return Cand(Role.EMPTY, 1.0)

    # 자동번호 라벨
    if label:
        if label.startswith("부속서"):
            return Cand(Role.ANNEX_HEADING, 0.95, parse_annex_heading(p))
        if re.fullmatch(r"비\s?고(\s*\d+)?", label):
            return Cand(Role.NOTE, 0.95)
        if re.fullmatch(r"보\s?기(\s*\d+)?", label):
            return Cand(Role.EXAMPLE, 0.95)
        if re.fullmatch(r"참\s?고(\s*\d+)?", label):
            return Cand(Role.REMARK, 0.95)
        if pt.LIST_LABEL_RE.match(label):
            return Cand(Role.LIST_ITEM, 0.9)
        heading_style = p.attrs.get("heading_level") is not None or _style_has(p, "[ksdt] a.1")
        if (_numeric_label(label) or _annex_clause_label(label)) and "본문용" not in sname:
            if heading_style or len(stripped) <= 80:
                number = label
                level = number.count(".") + 1
                return Cand(
                    Role.HEADING,
                    0.95 if heading_style else 0.75,
                    {"number": number, "level": level, "title": pt.clean(text)},
                )

    # 스타일 이름
    if "뒷표지" in sname:
        return Cand(Role.BACK_COVER, 0.9)
    if "[ksdt] 표지" in sname:
        return Cand(Role.COVER, 0.85)
    if _style_has(p, "[ksdt] 부속서 a", "[ksdt] 부속서 1") and stripped:
        return Cand(Role.ANNEX_HEADING, 0.9, parse_annex_heading(p))
    if _style_has(p, "표제목", "부표제목"):
        return Cand(Role.TABLE_CAPTION, 0.95)
    if _style_has(p, "그림제목", "부도제목"):
        return Cand(Role.FIGURE_CAPTION, 0.95)
    if "본문 규격번호" in sname or "본문 한국산업규격" in sname:
        return Cand(Role.STD_NUMBER, 0.95)
    if "규격서 제목 한글" in sname:
        return Cand(Role.TITLE_KO, 0.95)
    if "규격서 제목 영어" in sname:
        return Cand(Role.TITLE_EN, 0.95)
    if "[ksdt] 수식" in sname:
        return Cand(Role.FORMULA, 0.9)

    # 제목 텍스트(공백 제거 후 비교)
    title = _title_role(sq)
    if title is not None and len(stripped) <= 60:
        if title == Role.COMMENTARY_TITLE and not (
            p.attrs.get("jc") == "center" or p.attrs.get("bold") or "\n" in text
        ):
            title = None
        if title is not None:
            return Cand(title, 0.9)

    if stripped == "한국산업표준" or pt.STD_NUMBER_LINE_RE.match(stripped):
        return Cand(Role.STD_NUMBER, 0.9)

    # 부속서(손입력)
    m = pt.ANNEX_TEXT_RE.match(stripped)
    if m and len(stripped) <= 120 and not pt.is_sentence(stripped.split("\n")[-1]):
        return Cand(Role.ANNEX_HEADING, 0.85, parse_annex_heading(p))
    if pt.ANNEX_STATUS_RE.match(stripped):
        return Cand(Role.ANNEX_STATUS, 0.9, {"status": stripped.strip("() ")})

    # 비고·보기·참고
    if pt.NOTE_RE.match(stripped):
        return Cand(Role.NOTE, 0.85)
    if pt.EXAMPLE_RE.match(stripped):
        return Cand(Role.EXAMPLE, 0.85)
    if pt.REMARK_RE.match(stripped):
        return Cand(Role.REMARK, 0.85)

    if pt.UNIT_LABEL_RE.match(stripped):
        return Cand(Role.UNIT_LABEL, 0.95)
    if pt.TERM_SOURCE_RE.match(stripped):
        return Cand(Role.TERM_SOURCE, 0.9)

    # 그림·수식
    rest = text.replace(OBJ, "").strip()
    if p.has_drawing and not rest:
        return Cand(Role.FIGURE, 0.9)
    if p.has_math and pt.FORMULA_REST_RE.match(text.replace(OBJ, "")):
        return Cand(Role.FORMULA, 0.85)

    # 캡션
    cm = pt.caption_match(stripped)
    if cm and not pt.TOC_PAGE_RE.search(stripped):
        role = Role.TABLE_CAPTION if cm.group("kind") == "표" else Role.FIGURE_CAPTION
        if _style_has(p, "caption") or p.attrs.get("jc") == "center" or p.attrs.get("bold"):
            return Cand(role, 0.85, {"cap_num": cm.group("num")})
        if len(stripped) <= 60 and not pt.is_sentence(stripped):
            return Cand(role, 0.75, {"cap_num": cm.group("num")})

    # 목록
    if pt.LIST_TEXT_RE.match(stripped) or _style_has(p, "list", "번호매기기", "목록"):
        if not pt.TYPED_HEADING_RE.match(stripped):
            return Cand(Role.LIST_ITEM, 0.8)

    # 손으로 친 절 번호
    m = pt.TYPED_ANNEX_CLAUSE_RE.match(stripped)
    if m and "\n" not in stripped and len(m.group("title")) <= 60 and not pt.is_sentence(stripped):
        num = m.group("num")
        return Cand(
            Role.HEADING,
            0.8,
            {
                "number": num,
                "level": num.count(".") + 1,
                "title": m.group("title").strip(),
                "typed": True,
            },
        )
    m = pt.TYPED_HEADING_RE.match(stripped)
    if m and "\n" not in stripped:
        title_txt = m.group("title").strip()
        good_title = (
            len(title_txt) <= 60
            and not pt.is_sentence(title_txt)
            and re.match(r"[가-힣A-Z]", title_txt) is not None
            and "\t" not in title_txt
        )
        if good_title and (
            p.attrs.get("bold") or p.attrs.get("heading_level") or len(title_txt) <= 30
        ):
            num = m.group("num")
            return Cand(
                Role.HEADING,
                0.8 if p.attrs.get("bold") else 0.65,
                {"number": num, "level": num.count(".") + 1, "title": title_txt, "typed": True},
            )
    if pt.TERM_NUMBER_RE.match(stripped):
        return Cand(Role.TERM_NUMBER, 0.7)
    if p.attrs.get("heading_level") and "본문용" not in sname and not pt.is_sentence(stripped):
        return Cand(
            Role.HEADING,
            0.6,
            {"number": None, "level": p.attrs["heading_level"], "title": pt.clean(text)},
        )
    return None


def plausible_next(last: str | None, num: str) -> bool:
    """손으로 친 번호가 직전 절 번호 다음에 올 수 있는 번호인지(그림 범례 "1 용접봉" 등 배제)."""
    prefix = ""
    if num[:1].isalpha():
        prefix, num = num[:2], num[2:]
        if last and last[:1].isalpha():
            if last[:2] != prefix:
                return num == "1"
            last = last[2:]
        else:
            return num == "1"
    parts = [int(x) for x in num.split(".")]
    if not last:
        return parts == [1] or (prefix == "" and parts[0] <= 2 and len(parts) == 1)
    lp = [int(x) for x in last.split(".")]
    if parts == lp + [1]:
        return True
    for depth in range(len(lp)):
        if parts == lp[:depth] + [lp[depth] + 1]:
            return True
    return False


def _clause_kind(title: str) -> str:
    sq = pt.squash(title)
    if sq.startswith("적용범위"):
        return "scope"
    if sq.startswith(("인용표준", "인용규격")):
        return "normref"
    if "용어" in sq and "정의" in sq:
        return "terms"
    if sq.startswith(("기호와약어", "기호및약어", "기호")):
        return "symbols"
    return "body"


def _similar(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, pt.squash(a), pt.squash(b)).ratio()


def _cover_sections(doc: KSDoc, local: list[Cand | None]) -> tuple[int, int | None]:
    """(본문 앞부분이 시작하는 구역, 뒤표지 구역 또는 None)."""
    start_sec = 0
    for p, c in zip(doc.paras, local, strict=True):
        if c is None:
            continue
        if (
            c.role in FRONT_TITLES | {Role.STD_NUMBER, Role.TITLE_KO, Role.HEADING}
            and not p.in_table
        ):
            if c.role == Role.STD_NUMBER and p.section_idx == 0 and doc.meta.get("sections", 1) > 2:
                continue  # 표지의 표준번호
            start_sec = p.section_idx
            break
    last = doc.meta.get("sections", 1) - 1
    back = None
    if last >= 2 and last > start_sec:
        sec_paras = [(p, c) for p, c in zip(doc.paras, local, strict=True) if p.section_idx == last]
        content_roles = {Role.HEADING, Role.ANNEX_HEADING, Role.BIBLIO_TITLE, Role.COMMENTARY_TITLE}
        has_content = any(c is not None and c.role in content_roles for _, c in sec_paras)
        markers = any(
            (c is not None and c.role in (Role.BACK_COVER, Role.STD_NUMBER))
            or "Korean Agency" in p.text
            or "KATS" in p.text
            or re.search(r"\bICS\b", p.text)
            for p, c in sec_paras
        )
        nonempty = sum(1 for p, _ in sec_paras if p.text.strip())
        if not has_content and markers and nonempty <= 40:
            back = last
    return start_sec, back


class _Zones:
    """문서 흐름에 따라 구역(zone)을 바꾸며 역할을 확정한다."""

    def __init__(self, doc: KSDoc, local: list[Cand | None]):
        self.doc = doc
        self.local = local
        bp = boilerplate()
        self.normref_intro = bp["normref"]["intro"]
        self.terms_intros = [bp["terms"]["intro1"], bp["terms"]["intro2"].replace("{std}", "")]
        self.zone = "start"
        self.clause_kind = "body"
        self.pending: Role | None = None  # 다음 비어 있지 않은 문단에 줄 역할(이어지는 비고 등)
        self.after_term = False
        self.annex_wait: list[Role] = []
        self.last_heading_num: str | None = None

    def set(self, p: Para, role: Role, conf: float, attrs: dict | None = None) -> None:
        p.role = role
        p.role_conf = conf
        if attrs:
            p.attrs.update(attrs)
        p.attrs["zone"] = self.zone
        if self.zone in ("body", "annex"):
            p.attrs["clause_kind"] = self.clause_kind

    def run(self) -> None:
        start_sec, back_sec = _cover_sections(self.doc, self.local)
        for p, c in zip(self.doc.paras, self.local, strict=True):
            self.step(p, c, start_sec, back_sec)

    def step(self, p: Para, c: Cand | None, start_sec: int, back_sec: int | None) -> None:
        stripped = p.text.strip()
        empty = not stripped and not p.has_drawing and not p.num_label
        if p.section_idx < start_sec:
            self.zone = "cover" if p.section_idx == 0 else "cover_info"
            role = Role.EMPTY if empty else (Role.COVER if p.section_idx == 0 else Role.COVER_INFO)
            self.set(p, role, 0.9)
            return
        if back_sec is not None and p.section_idx >= back_sec:
            self.zone = "back_cover"
            self.set(p, Role.EMPTY if empty else Role.BACK_COVER, 0.9)
            return
        if empty:
            self.set(p, Role.EMPTY, 1.0)
            return
        role = c.role if c else None

        # 구역을 바꾸는 제목
        if role in ZONE_OF_TITLE and not p.in_table:
            self.zone = ZONE_OF_TITLE[role]
            self.pending = None
            self.set(p, role, c.conf)
            return
        if role == Role.ANNEX_HEADING and self.zone not in ("toc", "commentary") and not p.in_table:
            self.zone = "annex"
            self.clause_kind = "annex"
            self.pending = None
            attrs = dict(c.attrs)
            self.set(p, role, c.conf, attrs)
            self.annex_wait = []
            self.last_heading_num = None
            if not attrs.get("status"):
                self.annex_wait.append(Role.ANNEX_STATUS)
            if not attrs.get("annex_title"):
                self.annex_wait.append(Role.ANNEX_TITLE)
            self.current_annex = p
            return
        if role in (Role.STD_NUMBER, Role.TITLE_KO, Role.TITLE_EN) and self.zone in (
            "start",
            "toc",
            "foreword",
            "intro",
            "title",
        ):
            self.zone = "title"
            self.set(p, role, c.conf)
            return

        # 구역별 처리
        z = self.zone
        if z == "toc":
            if role == Role.TOC_ENTRY or pt.TOC_PAGE_RE.search(stripped) or p.attrs.get("in_toc"):
                self.set(p, Role.TOC_ENTRY, 0.9)
                return
            if role == Role.HEADING and not (c and c.attrs.get("typed")):
                self._enter_body(p, c)
                return
            self.set(p, Role.TOC_ENTRY, 0.6)
            return
        if z in ("foreword", "intro"):
            if role == Role.HEADING and (not c.attrs.get("typed") or self._is_first_clause(c)):
                self._enter_body(p, c)
                return
            self.set(p, Role.FOREWORD if z == "foreword" else Role.INTRO, 0.85)
            return
        if z == "title":
            if role == Role.HEADING:
                self._enter_body(p, c)
                return
            if p.in_table or len(stripped) <= 200:
                ratio = pt.hangul_ratio(stripped)
                if ratio >= 0.3:
                    self.set(p, Role.TITLE_KO, 0.75)
                else:
                    self.set(p, Role.TITLE_EN, 0.75)
                return
        if z == "commentary":
            self.set(p, Role.TABLE_CELL if p.in_table else Role.COMMENTARY, 0.85)
            return
        if z == "biblio":
            if p.in_table:
                self.set(p, Role.TABLE_CELL, 0.8)
            else:
                self.set(p, Role.BIBLIO_ENTRY, 0.85 if pt.BIBLIO_ENTRY_RE.match(stripped) else 0.7)
            return
        if z in ("start", "cover", "cover_info") and role == Role.HEADING:
            self._enter_body(p, c)
            return
        if z in ("body", "annex"):
            self._body(p, c)
            return
        # 시작 구역(구조를 알 수 없는 문서)
        if c is not None and c.role not in (Role.COVER, Role.BACK_COVER):
            self.set(p, c.role, min(c.conf, 0.6), c.attrs)
        else:
            self.set(p, Role.BODY, 0.5)

    def _is_first_clause(self, c: Cand) -> bool:
        return c.attrs.get("number") == "1" and _clause_kind(c.attrs.get("title", "")) == "scope"

    def _enter_body(self, p: Para, c: Cand) -> None:
        self.zone = "body"
        self._heading(p, c)

    def _heading(self, p: Para, c: Cand) -> None:
        attrs = dict(c.attrs)
        level = attrs.get("level") or 1
        if self.zone == "body" and level == 1:
            self.clause_kind = _clause_kind(attrs.get("title") or p.text)
        self.after_term = False
        self.pending = None
        if self.clause_kind == "terms" and level >= 2 and self.zone == "body":
            # 용어 항목: 자동번호 Heading + 줄바꿈 + 용어
            attrs["term"] = pt.clean(p.text)
            self.set(p, Role.TERM, c.conf, attrs)
            self.after_term = True
            return
        self.last_heading_num = attrs.get("number")
        self.set(p, Role.HEADING, c.conf, attrs)

    def _body(self, p: Para, c: Cand | None) -> None:
        stripped = p.text.strip()
        role = c.role if c else None
        if p.in_table:
            self.set(p, Role.TABLE_CELL, 0.9)
            return
        if self.annex_wait and self.zone == "annex":
            want = self.annex_wait[0]
            if want == Role.ANNEX_STATUS and role == Role.ANNEX_STATUS:
                self.annex_wait.pop(0)
                self.current_annex.attrs["status"] = c.attrs.get("status")
                self.set(p, Role.ANNEX_STATUS, 0.9, c.attrs)
                return
            if (
                want == Role.ANNEX_TITLE
                and role not in (Role.HEADING, Role.NOTE)
                and len(stripped) <= 80
            ):
                self.annex_wait = []
                self.current_annex.attrs["annex_title"] = pt.clean(stripped)
                self.set(p, Role.ANNEX_TITLE, 0.85)
                return
            self.annex_wait = []
        if role == Role.HEADING:
            typed = c.attrs.get("typed")
            num = c.attrs.get("number") or ""
            if typed and not plausible_next(self.last_heading_num, num):
                pass  # 번호가 이어지지 않는 손번호(그림 범례·목록 등)는 제목이 아니다
            elif self.zone == "annex" and typed and not re.match(r"[A-Z]\.", num):
                pass  # 부속서 안의 손번호 "1 ..."은 제목으로 보지 않는다
            else:
                self._heading(p, c)
                return
        if self.pending is not None and role not in (
            Role.HEADING,
            Role.NOTE,
            Role.EXAMPLE,
            Role.REMARK,
        ):
            pend = self.pending
            self.pending = None
            self.set(p, pend, 0.75)
            return
        if role in (Role.NOTE, Role.EXAMPLE, Role.REMARK):
            label_only = (
                re.fullmatch(r"(비\s?고|보\s?기|참\s?고)(\s*\d+)?\s*[:：]?", stripped) is not None
            )
            if label_only and not p.num_label:
                self.pending = role
            self.set(p, role, c.conf)
            return

        kind = self.clause_kind if self.zone == "body" else "annex"
        if kind == "normref":
            if (
                stripped == "해당사항 없음"
                or _similar(stripped, self.normref_intro) >= 0.5
                or stripped.startswith("다음의 인용표준")
            ):
                self.set(p, Role.NORMREF_INTRO, 0.9)
            else:
                self.set(p, Role.NORMREF_ENTRY, 0.85)
            return
        if kind == "terms":
            if (
                stripped == "해당사항 없음"
                or stripped.startswith("이 표준의 목적을 위하여")
                or max(_similar(stripped, t) for t in self.terms_intros) >= 0.6
            ):
                self.set(p, Role.TERMS_INTRO, 0.9)
                return
            if role == Role.TERM_NUMBER:
                self.set(p, Role.TERM_NUMBER, 0.85, {"number": stripped})
                self.pending = Role.TERM
                self.after_term = False
                return
            if role == Role.TERM_SOURCE:
                self.set(p, Role.TERM_SOURCE, 0.9)
                return
            if role == Role.LIST_ITEM:
                self.set(p, Role.LIST_ITEM, c.conf)
                return
            prev = self._prev_role(p)
            if prev == Role.TERM or (prev == Role.TERM_NUMBER):
                self.set(p, Role.DEFINITION, 0.8)
                return
            self.set(p, Role.BODY, 0.6)
            return

        if role in (
            Role.TABLE_CAPTION,
            Role.FIGURE_CAPTION,
            Role.FIGURE,
            Role.FORMULA,
            Role.UNIT_LABEL,
            Role.LIST_ITEM,
            Role.TERM_SOURCE,
        ):
            self.set(p, role, c.conf, c.attrs)
            return
        if role == Role.TERM_NUMBER:
            self.set(p, Role.BODY, 0.6)
            return
        self.set(p, Role.BODY, 0.8)

    def _prev_role(self, p: Para) -> Role | None:
        for q in reversed(self.doc.paras[: p.idx]):
            if q.role == Role.EMPTY or q.in_table:
                continue
            return q.role
        return None


def classify_roles(doc: KSDoc) -> None:
    local = [local_candidate(p) for p in doc.paras]
    for p, c in zip(doc.paras, local, strict=True):
        p.attrs["local_role"] = c.role.value if c else None
    _Zones(doc, local).run()
    # 용어 항목이 손번호 + 다음 문단인 경우(TERM_NUMBER → TERM)
    for i, p in enumerate(doc.paras):
        if p.role == Role.TERM and "term" not in p.attrs:
            p.attrs["term"] = pt.clean(p.text)
        if p.role == Role.TERM_NUMBER:
            for q in doc.paras[i + 1 :]:
                if q.role == Role.EMPTY:
                    continue
                if q.role == Role.TERM:
                    q.attrs.setdefault("number", pt.clean(p.text))
                break
