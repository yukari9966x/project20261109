"""구조·요소 규칙: STR-01(필수 요소), STR-02(순서), STR-03(미결문단), STR-04(참고 요소의 요구 표현), STR-06."""

from __future__ import annotations

import re

from ksfix.classify.tree import Node
from ksfix.model.ir import KSDoc, Para, Role
from ksfix.rules.base import FixSpec
from ksfix.rules.context import RuleContext
from ksfix.rules.packs.ksa0001_2023.common import finding, first_clause, similarity
from ksfix.rules.registry import rule


def _first(doc: KSDoc, *roles: Role) -> Para | None:
    want = set(roles)
    return next((p for p in doc.paras if p.role in want), None)


def _has_structure(doc: KSDoc) -> bool:
    return any(p.role == Role.HEADING for p in doc.paras)


@rule("STR-01")
def required_elements(doc: KSDoc, ctx: RuleContext):
    if not _has_structure(doc):
        return
    anchor = _first(doc, Role.TITLE_KO) or _first(doc, Role.STD_NUMBER) or _first(doc, Role.HEADING)
    checks = [
        ("머리말", _first(doc, Role.FOREWORD_TITLE)),
        ("국문 제목", _first(doc, Role.TITLE_KO)),
        ("영문 제목", _first(doc, Role.TITLE_EN)),
        ("1 적용범위", first_clause(doc, "scope")),
        ("2 인용표준", first_clause(doc, "normref")),
        ("3 용어와 정의", first_clause(doc, "terms")),
    ]
    for name, found in checks:
        if found is None:
            yield finding(
                ctx,
                "STR-01",
                anchor,
                None,
                None,
                f"필수 요소가 없습니다: {name}.",
                fix=FixSpec("insert_paragraph_after", anchor.idx, text=name, auto=False),
                suggestion=f"'{name}' 요소를 KS A 0001 5.1.3 표 3의 위치에 넣습니다.",
                missing=name,
            )


ORDER = [
    ("toc", "목차"),
    ("foreword", "머리말"),
    ("intro", "개요"),
    ("title", "제목"),
    ("scope", "적용범위"),
    ("normref", "인용표준"),
    ("terms", "용어와 정의"),
    ("body", "본문 절"),
    ("annex", "부속서"),
    ("commentary", "해설"),
]
RANK = {k: i for i, (k, _) in enumerate(ORDER)}
NAME = dict(ORDER)


def _marker(p: Para) -> str | None:
    if p.role == Role.TOC_TITLE:
        return "toc"
    if p.role == Role.FOREWORD_TITLE:
        return "foreword"
    if p.role == Role.INTRO_TITLE:
        return "intro"
    if p.role in (Role.STD_NUMBER, Role.TITLE_KO):
        return "title"
    if (
        p.role == Role.HEADING
        and (p.attrs.get("level") or 1) == 1
        and p.attrs.get("zone") == "body"
    ):
        kind = p.attrs.get("clause_kind", "body")
        return kind if kind in RANK else "body"
    if p.role == Role.ANNEX_HEADING:
        return "annex"
    if p.role == Role.COMMENTARY_TITLE:
        return "commentary"
    return None


@rule("STR-02")
def element_order(doc: KSDoc, ctx: RuleContext):
    """앞 요소보다 순서가 이른 요소가 뒤에 나오면 그 요소에 지적(참고문헌 위치는 STR-06)."""
    best = -1
    best_name = ""
    seen: set[str] = set()
    for p in doc.paras:
        m = _marker(p)
        if m is None or (m in seen and m not in ("body",)):
            continue
        seen.add(m)
        r = RANK[m]
        if r < best:
            yield finding(
                ctx,
                "STR-02",
                p,
                None,
                None,
                f"요소 순서가 맞지 않습니다: '{NAME[m]}'은(는) '{best_name}'보다 앞에 와야 합니다.",
                element=NAME[m],
            )
        elif r > best:
            best, best_name = r, NAME[m]


HANG_EXEMPT = {"scope", "normref", "terms", "symbols"}


def _walk(node: Node):
    for ch in node.children:
        yield ch
        yield from _walk(ch)


@rule("STR-03")
def hanging_paragraphs(doc: KSDoc, ctx: RuleContext):
    if doc.tree is None:
        return
    for node in _walk(doc.tree):
        if node.kind != "clause" or not node.children or node.para_idx is None:
            continue
        head = doc.paras[node.para_idx]
        kind = head.attrs.get("clause_kind")
        if node.level == 1 and kind in HANG_EXEMPT:
            continue
        first_child = node.children[0].para_idx
        for q in doc.paras[node.para_idx + 1 : first_child]:
            if q.role in (Role.EMPTY,):
                continue
            label = node.number or ""
            yield finding(
                ctx,
                "STR-03",
                q,
                None,
                None,
                f"미결문단입니다: {label} 제목과 첫 하위 항 사이에 번호 없는 문단이 있습니다.",
                fix=FixSpec(
                    "insert_paragraph_before", q.idx, text=f"{label}.1 일반사항", auto=False
                ),
                suggestion=f"'{label}.1 일반사항' 항을 새로 만들어 이 문단을 옮깁니다.",
            )
            break


# 요구·권고·허용 표현(간접 인용 '…하여야 한다고'는 제외)
REQ_RE = re.compile(
    r"(?:하여야|해야|어야|여야)\s*(?:한다|하며|하고|함)(?!고)|"
    r"(?:하여서는|해서는|어서는)\s*안\s*된다(?!고)|"
    r"것이\s*좋다(?!고)|하여야\s*할\s*것이다|"
    r"(?:해도|하여도|어도)\s*된다(?!고)|할\s*필요가\s*없다(?!고)"
)
QUOTE_RE = re.compile(r"“[^”]*”|\"[^\"]*\"|‘[^’]*’|'[^']*'|「[^」]*」")
INFORMATIVE = {
    "foreword": "머리말",
    "intro": "개요",
    "scope": "적용범위",
    "commentary": "해설",
}


@rule("STR-04")
def informative_requirements(doc: KSDoc, ctx: RuleContext):
    white = ctx.whitelist()
    annex_status: str | None = None
    for p in doc.paras:
        if p.role == Role.ANNEX_HEADING:
            annex_status = p.attrs.get("status")
            continue
        zone = p.attrs.get("zone")
        where = None
        severity = None
        if p.role in (Role.NOTE, Role.EXAMPLE, Role.REMARK):
            where = {Role.NOTE: "비고", Role.EXAMPLE: "보기", Role.REMARK: "참고"}[p.role]
        elif zone in ("foreword", "intro", "commentary") and p.role in (
            Role.FOREWORD,
            Role.INTRO,
            Role.COMMENTARY,
        ):
            where = INFORMATIVE[zone]
        elif (
            zone == "body"
            and p.attrs.get("clause_kind") == "scope"
            and p.role
            in (
                Role.BODY,
                Role.LIST_ITEM,
            )
        ):
            where = "적용범위"
        elif zone == "annex" and annex_status == "참고" and p.role in (Role.BODY, Role.LIST_ITEM):
            where, severity = "참고 부속서", "warning"
        if where is None:
            continue
        if any(similarity(p.text, w) >= 0.85 for w in white):
            continue
        quotes = [(q.start(), q.end()) for q in QUOTE_RE.finditer(p.text)]
        m = next(
            (x for x in REQ_RE.finditer(p.text) if not any(a <= x.start() < b for a, b in quotes)),
            None,
        )
        if not m:
            continue
        msg = f"{where}에는 요구·권고·허용 표현('{m.group()}')을 쓰지 않습니다."
        if severity == "warning":
            msg = f"참고 부속서에 요구·권고·허용 표현('{m.group()}')이 있습니다. 선택적 요구사항인지 확인하세요."
        yield finding(ctx, "STR-04", p, m.start(), m.end(), msg, severity=severity, where=where)


@rule("STR-06")
def bibliography_last(doc: KSDoc, ctx: RuleContext):
    bib = _first(doc, Role.BIBLIO_TITLE)
    if bib is None:
        return
    later = [p for p in doc.paras[bib.idx + 1 :] if p.role == Role.ANNEX_HEADING]
    if later:
        yield finding(
            ctx,
            "STR-06",
            bib,
            None,
            None,
            f"참고문헌은 마지막 부속서 뒤에 둡니다(뒤에 부속서 {len(later)}개가 있음).",
        )
