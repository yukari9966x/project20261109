"""정형문 규칙: BLT-03(인용표준), BLT-04(용어와 정의)."""

from __future__ import annotations

import re

from ksfix.classify import patterns as pt
from ksfix.model.ir import KSDoc, Para, Role
from ksfix.rules.base import FixSpec
from ksfix.rules.context import RuleContext
from ksfix.rules.packs.ksa0001_2023.common import (
    clause_paras,
    finding,
    first_clause,
    same_text,
    similarity,
)
from ksfix.rules.registry import rule

NONE_TEXT = "해당사항 없음"
AUTO_RATIO = 0.85
MISSING_RATIO = 0.5


def _check_intro(
    ctx: RuleContext,
    rid: str,
    heading: Para,
    body: list[Para],
    intro_role: Role,
    entry_roles: set[Role],
    targets: list[str],
    accept: re.Pattern[str] | None,
    what: str,
):
    intros = [p for p in body if p.role == intro_role and not p.in_table]
    entries = [p for p in body if p.role in entry_roles]
    none_paras = [p for p in intros if pt.clean(p.text) == NONE_TEXT]
    real = [p for p in intros if pt.clean(p.text) != NONE_TEXT]
    target = targets[0]
    insert_none = not entries and not none_paras
    if not real:
        text = target + (f"\n{NONE_TEXT}" if insert_none else "")
        anchor = none_paras[0] if none_paras else heading
        kind = "insert_paragraph_before" if none_paras else "insert_paragraph_after"
        yield finding(
            ctx,
            rid,
            heading,
            None,
            None,
            f"{what} 도입 정형문이 없습니다.",
            fix=FixSpec(kind, anchor.idx, text=text, style="body"),
            suggestion=text,
        )
        return
    p = real[0]
    text = pt.clean(p.text)
    ok = any(same_text(text, t) for t in targets) or (accept is not None and accept.match(text))
    if not ok:
        best = max(targets, key=lambda t: similarity(text, t))
        ratio = similarity(text, best)
        auto = ratio >= AUTO_RATIO
        msg = (
            f"{what} 도입 정형문의 문구가 KS A 0001과 다릅니다(유사도 {ratio:.2f})."
            if ratio >= MISSING_RATIO
            else f"{what} 도입 정형문이 KS A 0001 문구와 크게 다릅니다(유사도 {ratio:.2f})."
        )
        yield finding(
            ctx,
            rid,
            p,
            0,
            len(p.text),
            msg,
            fix=FixSpec("replace_text", p.idx, 0, len(p.text.rstrip()), text=best, auto=auto),
            suggestion=best,
            confidence=round(ratio, 2),
        )
    if insert_none:
        yield finding(
            ctx,
            rid,
            p,
            None,
            None,
            f"{what}이(가) 없으면 정형문 아래에 '{NONE_TEXT}'을 적습니다.",
            fix=FixSpec("insert_paragraph_after", p.idx, text=NONE_TEXT, style="body"),
            suggestion=NONE_TEXT,
        )


@rule("BLT-03")
def normref_intro(doc: KSDoc, ctx: RuleContext):
    heading = first_clause(doc, "normref")
    if heading is None:
        return
    bp = ctx.boilerplate["normref"]["intro"]
    yield from _check_intro(
        ctx,
        "BLT-03",
        heading,
        clause_paras(doc, heading),
        Role.NORMREF_INTRO,
        {Role.NORMREF_ENTRY},
        [bp],
        None,
        "인용표준",
    )


TERMS2_RE = re.compile(
    r"^이 표준의 목적을 위하여 (?P<std>.+?)에 규정된 용어와 정의 및 다음을 적용한다\.?$"
)


@rule("BLT-04")
def terms_intro(doc: KSDoc, ctx: RuleContext):
    heading = first_clause(doc, "terms")
    if heading is None:
        return
    bp = ctx.boilerplate["terms"]
    body = clause_paras(doc, heading)
    targets = [bp["intro1"]]
    first = next(
        (p for p in body if p.role == Role.TERMS_INTRO and pt.clean(p.text) != NONE_TEXT), None
    )
    if first is not None:
        text = pt.clean(first.text)
        m = re.match(r"^이 표준의 목적을 위하여 (?P<std>.+?)에 규정된", text)
        cited = m.group("std") if m else None
        if cited is None:
            stds = [s.group().strip() for s in pt.STD_NO_RE.finditer(text)]
            if stds:
                cited = stds[0] if len(stds) == 1 else ", ".join(stds[:-1]) + " 및 " + stds[-1]
        if cited:
            targets.insert(0, bp["intro2"].replace("{std}", cited))
    yield from _check_intro(
        ctx,
        "BLT-04",
        heading,
        body,
        Role.TERMS_INTRO,
        {Role.TERM, Role.TERM_NUMBER},
        targets,
        TERMS2_RE,
        "용어와 정의",
    )
