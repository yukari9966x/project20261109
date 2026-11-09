"""참조 규칙: REF-01(참조 대상 존재)."""

from __future__ import annotations

import re

from ksfix.classify import patterns as pt
from ksfix.model.ir import KSDoc, Para, Role
from ksfix.rules.context import RuleContext
from ksfix.rules.packs.ksa0001_2023.common import finding
from ksfix.rules.registry import rule

REF_ROLES = {
    Role.BODY,
    Role.LIST_ITEM,
    Role.NOTE,
    Role.EXAMPLE,
    Role.REMARK,
    Role.DEFINITION,
    Role.TABLE_CELL,
    Role.INTRO,
    Role.COMMENTARY,
}

CLAUSE_RE = re.compile(r"(?<![\w.\-:/])(?P<num>(?:[A-Z]\.)?[1-9]\d?(?:\.\d{1,3}){1,5})(?![\d.]*\d)")
# 절 번호 뒤에 와야 하는 말(이것이 없으면 소수 값일 가능성이 높다)
CLAUSE_AFTER_RE = re.compile(
    r"^\s*(?:항|절)?\s*(?:에서|에|의|을|를|과|와|으로|로|부터|까지|참조|및|또는)"
)
RANGE_AFTER_RE = re.compile(r"^\s*[∼~～]\s*(?:[A-Z]\.)?\d+(?:\.\d+)+\s*(?:의|에|을|를|과|와)")
TABLE_REF_RE = re.compile(r"(?<![\w])표\s*(?P<num>(?:[A-Z]\.)?\d+)(?![\d.]*\d)")
FIGURE_REF_RE = re.compile(r"(?<![\w])그림\s*(?P<num>(?:[A-Z]\.)?\d+)(?![\d.]*\d)")
ANNEX_REF_RE = re.compile(r"(?<![\w])부속서\s*(?P<num>[A-Z])(?![A-Za-z])")
FORMULA_REF_RE = re.compile(r"(?<![\w])식\s*\(\s*(?P<num>(?:[A-Z]\.)?\d+[a-z]?)\s*\)")
FORMULA_NUM_RE = re.compile(r"\(\s*((?:[A-Z]\.)?\d+[a-z]?)\s*\)\s*$")
# 다른 표준의 요소 참조: "IEC 60974-1:2017의 표 6", "KS C IEC 60384-1:2016의 2.4와 2.5"
OTHER_STD_TAIL_RE = re.compile(
    rf"(?:{pt.STD_NO_CORE})(?:\s*[:：]\s*\d{{4}})?\s*의\s*(?:(?:표|그림|부속서|식)?\s*[A-Z0-9.()]+\s*(?:와|과|및|,|또는|∼|~)\s*)*(?:표|그림|부속서|식)?\s*$"
)


def known_targets(doc: KSDoc) -> dict[str, set[str]]:
    clauses: set[str] = set()
    tables: set[str] = set()
    figures: set[str] = set()
    annexes: set[str] = set()
    formulas: set[str] = set()
    for p in doc.paras:
        if p.role == Role.HEADING and p.attrs.get("number"):
            clauses.add(p.attrs["number"])
        elif p.role in (Role.TERM, Role.TERM_NUMBER) and p.attrs.get("number"):
            clauses.add(p.attrs["number"])
        elif p.role == Role.ANNEX_HEADING and p.attrs.get("letter"):
            annexes.add(p.attrs["letter"])
        elif p.role in (Role.TABLE_CAPTION, Role.FIGURE_CAPTION):
            m = pt.CAPTION_RE.match(p.text.strip())
            if m:
                (tables if m.group("kind") == "표" else figures).add(m.group("num"))
        elif p.role == Role.FORMULA:
            m = FORMULA_NUM_RE.search(p.text.replace("￼", " "))
            if m:
                formulas.add(m.group(1))
    # 부속서 번호 A가 있으면 하위 절(A.1)이 없더라도 'A'는 존재
    return {
        "clause": clauses,
        "table": tables,
        "figure": figures,
        "annex": annexes,
        "formula": formulas,
    }


OTHER_DOC_TAIL_RE = re.compile(
    r"(?<!이 )(?:규격|표준|지침|가이드|문서|시방서)의\s*(?:표|그림|부속서|식)?\s*$"
)


def other_standard(text: str, start: int) -> bool:
    window = text[max(0, start - 80) : start]
    return (
        OTHER_STD_TAIL_RE.search(window) is not None or OTHER_DOC_TAIL_RE.search(window) is not None
    )


def _iter_refs(p: Para):
    text = p.text
    for m in CLAUSE_RE.finditer(text):
        after = text[m.end() : m.end() + 12]
        if not (CLAUSE_AFTER_RE.match(after) or RANGE_AFTER_RE.match(text[m.end() :])):
            continue
        before = text[max(0, m.start() - 4) : m.start()]
        if re.search(r"(?:표|그림|식\s*\(|부속서)\s*$", before):
            continue
        yield "clause", m.group("num"), m.start(), m.end()
    for kind, regex in (
        ("table", TABLE_REF_RE),
        ("figure", FIGURE_REF_RE),
        ("annex", ANNEX_REF_RE),
        ("formula", FORMULA_REF_RE),
    ):
        for m in regex.finditer(text):
            yield kind, m.group("num"), m.start(), m.end()


KIND_KO = {"clause": "절·항", "table": "표", "figure": "그림", "annex": "부속서", "formula": "식"}


@rule("REF-01")
def reference_targets(doc: KSDoc, ctx: RuleContext):
    known = known_targets(doc)
    for p in doc.paras:
        if p.role not in REF_ROLES:
            continue
        for kind, num, start, end in _iter_refs(p):
            if kind == "formula" and not known["formula"]:
                continue  # 식 번호를 읽지 못한 문서는 건너뜀(오탐 방지)
            if kind == "clause" and p.role == Role.TABLE_CELL:
                continue
            if num in known[kind]:
                continue
            if other_standard(p.text, start):
                continue
            label = {"clause": num, "table": f"표 {num}", "figure": f"그림 {num}"}.get(
                kind, f"부속서 {num}" if kind == "annex" else f"식 ({num})"
            )
            yield finding(
                ctx,
                "REF-01",
                p,
                start,
                end,
                f"참조한 {KIND_KO[kind]} '{label}'이(가) 이 문서에 없습니다.",
                ref_kind=kind,
                ref=num,
            )
