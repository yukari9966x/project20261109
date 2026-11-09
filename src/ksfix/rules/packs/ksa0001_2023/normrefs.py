"""인용표준·참고문헌 규칙: NRF-01(순서), NRF-02(본문 인용 표준 누락), NRF-03(법규 금지)."""

from __future__ import annotations

import re

from ksfix.classify import patterns as pt
from ksfix.model.ir import KSDoc, Role
from ksfix.rules.context import RuleContext
from ksfix.rules.packs.ksa0001_2023.common import finding
from ksfix.rules.registry import rule

CAT_NAME = ["국가표준(KS)", "국제표준(ISO·IEC)", "가이드", "단체표준 등"]


def category(text: str) -> int:
    t = text.strip()
    if re.match(r"^KS\s?[A-Z]\b", t):
        return 0
    if re.match(r"^(ISO/IEC|ISO|IEC)\s+Guide", t, re.I):
        return 2
    if re.match(r"^(ISO/IEC|ISO|IEC|ITU)\b", t):
        return 1
    return 3


@rule("NRF-01")
def normref_order(doc: KSDoc, ctx: RuleContext):
    best = -1
    for p in doc.by_role(Role.NORMREF_ENTRY):
        if not pt.STD_NO_RE.match(p.text.strip()):
            continue
        c = category(p.text)
        if c < best:
            yield finding(
                ctx,
                "NRF-01",
                p,
                None,
                None,
                f"인용표준은 국가표준 → 국제표준 → 가이드 → 단체표준 순서로 적습니다({CAT_NAME[c]}가 {CAT_NAME[best]} 뒤에 있음).",
            )
        best = max(best, c)


def base_no(std: str) -> str:
    s = re.sub(r"\s*[:：]\s*\d{4}.*$", "", std)
    return re.sub(r"\s+", "", s).upper()


CITE_ROLES = {
    Role.BODY, Role.LIST_ITEM, Role.NOTE, Role.EXAMPLE, Role.REMARK, Role.DEFINITION,
    Role.TABLE_CELL, Role.TERM_SOURCE, Role.TABLE_CAPTION, Role.FIGURE_CAPTION,
}  # fmt: skip


@rule("NRF-02")
def cited_standards_listed(doc: KSDoc, ctx: RuleContext):
    listed: set[str] = set()
    for p in doc.paras:
        if p.role in (Role.NORMREF_ENTRY, Role.BIBLIO_ENTRY):
            for m in pt.STD_NO_RE.finditer(p.text):
                listed.add(base_no(m.group()))
    own = base_no(doc.meta.get("std_number") or "")
    original = re.sub(r"^KS[A-Z]", "", own) if re.match(r"^KS[A-Z](ISO|IEC)", own) else own
    reported: set[str] = set()
    for p in doc.paras:
        if p.role not in CITE_ROLES:
            continue
        for m in pt.STD_NO_RE.finditer(p.text):
            b = base_no(m.group())
            if not re.search(r"\d", b) or b in (own, original) or b in reported:
                continue
            if b in listed or any(b.startswith(x) or x.startswith(b) for x in listed if len(x) > 4):
                continue
            reported.add(b)
            yield finding(
                ctx,
                "NRF-02",
                p,
                m.start(),
                m.end(),
                f"본문에서 인용한 {m.group().strip()}이(가) 인용표준이나 참고문헌에 없습니다.",
            )


LAW_RE = re.compile(r"법률|시행령|시행규칙|고시\s*제\s*\d|훈령|조례|기술규정|「[^」]*법[^」]*」")
LAW_NAME_RE = re.compile(r"[가-힣]+(?:관리|안전|진흥|촉진|표준화|규제|보호|기본|특별|에 관한)\s?법")


@rule("NRF-03")
def no_laws_in_normrefs(doc: KSDoc, ctx: RuleContext):
    """법령 어휘가 있거나, 표준번호로 시작하지 않으면서 법령 이름 꼴인 항목."""
    for p in doc.by_role(Role.NORMREF_ENTRY):
        text = p.text.strip()
        m = LAW_RE.search(text)
        if m is None and not pt.STD_NO_RE.match(text):
            m = LAW_NAME_RE.search(text)
        if m:
            yield finding(
                ctx,
                "NRF-03",
                p,
                m.start(),
                m.end(),
                "법규·기술규정은 인용표준에 넣지 않습니다. 필요하면 참고문헌에 적습니다.",
            )
