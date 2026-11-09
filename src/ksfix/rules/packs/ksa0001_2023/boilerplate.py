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


def _best_match(paras: list[Para], targets: list[str]) -> tuple[Para | None, str, float]:
    best = (None, targets[0], 0.0)
    for p in paras:
        for t in targets:
            r = similarity(pt.clean(p.text), t)
            if r > best[2]:
                best = (p, t, r)
    return best


@rule("BLT-02")
def foreword_copyright(doc: KSDoc, ctx: RuleContext):
    """머리말 저작권 정형문 2문장 + 특허 정형문(두 형태 허용)."""
    title = next((p for p in doc.paras if p.role == Role.FOREWORD_TITLE), None)
    if title is None:
        return
    body = [p for p in doc.paras if p.role == Role.FOREWORD and pt.clean(p.text)]
    bp = ctx.boilerplate["foreword"]
    required = [
        ("저작권 정형문(첫째 문장)", [bp["copyright"][0]]),
        ("저작권 정형문(둘째 문장)", [bp["copyright"][1]]),
        ("특허 정형문", list(bp["patent"])),
    ]
    used: set[int] = set()
    last_anchor = body[0] if body else title
    for name, targets in required:
        p, target, ratio = _best_match([q for q in body if q.idx not in used], targets)
        if p is not None and ratio >= MISSING_RATIO:
            used.add(p.idx)
            last_anchor = p
            if any(same_text(p.text, t) for t in targets):
                continue
            auto = ratio >= AUTO_RATIO
            yield finding(
                ctx,
                "BLT-02",
                p,
                0,
                len(p.text),
                f"머리말 {name}의 문구가 KS A 0001 부속서 E와 다릅니다(유사도 {ratio:.2f}).",
                fix=FixSpec("replace_text", p.idx, 0, len(p.text.rstrip()), text=target, auto=auto),
                suggestion=target,
                confidence=round(ratio, 2),
            )
        else:
            yield finding(
                ctx,
                "BLT-02",
                title,
                None,
                None,
                f"머리말에 {name}이(가) 없습니다.",
                fix=FixSpec(
                    "insert_paragraph_after", last_anchor.idx, text=targets[0], style="body"
                ),
                suggestion=targets[0],
            )


@rule("BLT-06")
def commentary_intro(doc: KSDoc, ctx: RuleContext):
    title = next((p for p in doc.paras if p.role == Role.COMMENTARY_TITLE), None)
    if title is None:
        return
    target = ctx.boilerplate["commentary"]["intro"]
    accepted = [target, *ctx.boilerplate["commentary"].get("accepted", [])]
    body = [
        p for p in doc.paras[title.idx + 1 :] if p.role == Role.COMMENTARY and pt.clean(p.text)
    ][:3]
    if any(same_text(q.text, a) for q in body for a in accepted):
        return
    p, _, ratio = _best_match(body, [target])
    if p is not None and ratio >= MISSING_RATIO:
        yield finding(
            ctx,
            "BLT-06",
            p,
            0,
            len(p.text),
            f"해설 도입문의 문구가 KS A 0001 부속서 N과 다릅니다(유사도 {ratio:.2f}).",
            fix=FixSpec(
                "replace_text",
                p.idx,
                0,
                len(p.text.rstrip()),
                text=target,
                auto=ratio >= AUTO_RATIO,
            ),
            suggestion=target,
        )
        return
    yield finding(
        ctx,
        "BLT-06",
        title,
        None,
        None,
        "해설 도입문(이 해설은 … 표준의 일부는 아니다.)이 없습니다.",
        fix=FixSpec("insert_paragraph_after", title.idx, text=target, style="body"),
        suggestion=target,
    )
