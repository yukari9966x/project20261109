"""조항의 문장 말미 규칙(부속서 I): VRB-01(반드시), VRB-02(할 수 있다 — 허용/가능성 판정)."""

from __future__ import annotations

import re

from ksfix.model.ir import KSDoc, Role
from ksfix.rules.base import FixSpec
from ksfix.rules.context import RuleContext
from ksfix.rules.packs.ksa0001_2023.common import finding, similarity
from ksfix.rules.registry import rule

# 받침이 ㄹ인 한글 음절(할·될·바꿀·을 …) + " 수 있다"
RIEUL = "".join(chr(c) for c in range(0xAC00, 0xD7A4) if (c - 0xAC00) % 28 == 8)
CAN_RE = re.compile(rf"[가-힣]*[{RIEUL}]\s*수\s*있(?:다|으며|고|음|습니다)(?![가-힣])")
MUST_RE = re.compile(r"반드시\s+")
REQ_END_RE = re.compile(r"(?:하여야|해야|어야|여야|야)\s*(?:한다|하며|하고|할|함)")
SENTENCE_RE = re.compile(r"[^.?!。]*[.?!。]?")

VERB_ROLES = {Role.BODY, Role.LIST_ITEM, Role.TABLE_CELL, Role.DEFINITION}


def _whitelisted(ctx: RuleContext, text: str) -> bool:
    return any(similarity(text, w) >= 0.85 for w in ctx.whitelist())


def sentences(text: str):
    for m in SENTENCE_RE.finditer(text):
        if m.group().strip():
            yield m.start(), m.end(), m.group()


@rule("VRB-01")
def must_external(doc: KSDoc, ctx: RuleContext):
    for p in doc.paras:
        if p.role not in VERB_ROLES | {Role.NOTE, Role.EXAMPLE, Role.REMARK}:
            continue
        for s0, _s1, sent in sentences(p.text):
            m = MUST_RE.search(sent)
            if not m or not REQ_END_RE.search(sent[m.end() :]):
                continue
            a, b = s0 + m.start(), s0 + m.end()
            yield finding(
                ctx,
                "VRB-01",
                p,
                a,
                b,
                "'반드시 ~하여야 한다'는 법령 등 문서 밖의 의무(외적 제약)에만 씁니다. "
                "이 표준의 요구사항이면 '반드시'를 뺍니다.",
                fix=FixSpec("replace_text", p.idx, a, b, text="", auto=False),
                suggestion=(sent[: m.start()] + sent[m.end() :]).strip(),
                confidence=0.7,
            )


@rule("VRB-02")
def can_permission(doc: KSDoc, ctx: RuleContext):
    """LLM이 없으면 '판단 필요(info)'로만 표시한다(허용이면 '~해도 된다')."""
    for p in doc.paras:
        if p.role not in VERB_ROLES:
            continue
        if _whitelisted(ctx, p.text):
            continue
        for m in CAN_RE.finditer(p.text):
            yield finding(
                ctx,
                "VRB-02",
                p,
                m.start(),
                m.end(),
                f"'{m.group()}'이(가) 허용(…해도 된다)의 뜻인지 가능성·역량(…할 수 있다)의 뜻인지 확인이 필요합니다.",
                severity="info",
                confidence=0.5,
                needs_judgement=True,
            )
