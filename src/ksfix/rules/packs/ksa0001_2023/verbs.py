"""조항의 문장 말미 규칙(부속서 I): VRB-01(반드시), VRB-02(할 수 있다 — 허용/가능성), VRB-04(금지 표현).

LLM이 꺼져 있으면 VRB-02는 '판단 필요(info)'만 표시한다. LLM이 켜져 있으면 T1 판정으로
허용 의미인 문장은 '~해도 된다'로 고친 문장을 제안(AI 제안)하고, 가능성·역량이면 지적하지 않는다.
"""

from __future__ import annotations

import re

from ksfix.model.ir import KSDoc, Para, Role
from ksfix.rules.base import Finding, FixSpec
from ksfix.rules.context import RuleContext
from ksfix.rules.packs.ksa0001_2023.common import finding, similarity
from ksfix.rules.registry import rule

# 받침이 ㄹ인 한글 음절(할·될·바꿀·을 …) + " 수 있다"
RIEUL = "".join(chr(c) for c in range(0xAC00, 0xD7A4) if (c - 0xAC00) % 28 == 8)
CAN_RE = re.compile(rf"[가-힣]*[{RIEUL}]\s*수\s*있(?:다|으며|고|음|습니다)(?![가-힣])")
MUST_RE = re.compile(r"반드시\s+")
REQ_END_RE = re.compile(r"(?:하여야|해야|어야|여야|야)\s*(?:한다|하며|하고|할|함)")
FORBID_RE = re.compile(
    r"(?P<verb>[가-힣]+?)(?:하면|면)\s*안\s*된다|(?P<verb2>[가-힣]+?)지\s*말\s*것"
)

VERB_ROLES = {Role.BODY, Role.LIST_ITEM, Role.TABLE_CELL, Role.DEFINITION}
NOTE_ROLES = {Role.NOTE, Role.EXAMPLE, Role.REMARK}


def _whitelisted(ctx: RuleContext, text: str) -> bool:
    return any(similarity(text, w) >= 0.85 for w in ctx.whitelist())


def _candidates(doc: KSDoc, ctx: RuleContext) -> list[dict]:
    """VRB-01·VRB-02 후보 문장(문단·문장 위치 포함)."""
    from ksfix.llm.tasks.modal_verbs import split_sentences

    if "modal_cands" in ctx.memo:
        return ctx.memo["modal_cands"]
    out = []
    for p in doc.paras:
        if p.role not in VERB_ROLES | NOTE_ROLES or _whitelisted(ctx, p.text):
            continue
        for s0, s1, sent in split_sentences(p.text):
            kinds = []
            m = MUST_RE.search(sent)
            if m and REQ_END_RE.search(sent[m.end() :]):
                kinds.append("VRB-01")
            if p.role in VERB_ROLES and CAN_RE.search(sent):
                kinds.append("VRB-02")
            if kinds:
                out.append(
                    {
                        "id": f"p{p.idx}s{s0}",
                        "para": p.idx,
                        "start": s0,
                        "end": s1,
                        "text": sent,
                        "kinds": kinds,
                        "where": p.clause_no or p.attrs.get("zone", ""),
                        "role": p.role.value,
                    }
                )
    ctx.memo["modal_cands"] = out
    return out


def _judgments(doc: KSDoc, ctx: RuleContext) -> dict:
    """LLM T1 판정(규칙 실행 한 번에 한 번만 호출)."""
    if ctx.llm is None:
        return {}
    if "modal_judgments" not in ctx.memo:
        from ksfix.llm.tasks.modal_verbs import judge

        cands = _candidates(doc, ctx)
        js = judge(ctx.llm, cands) if cands else {}
        ctx.memo["modal_judgments"] = js
        stats = {"judged": len(js), "model": getattr(ctx.llm, "model", None)}
        for j in js.values():
            stats[j.category] = stats.get(j.category, 0) + 1
            if j.rejected and j.rejected.startswith("LLM 오류"):
                stats["errors"] = stats.get("errors", 0) + 1
                stats.setdefault("error", j.rejected)
        doc.meta["llm_modal"] = stats
    return ctx.memo["modal_judgments"]


def _llm_finding(ctx: RuleContext, rid: str, p: Para, c: dict, j, message: str) -> Finding:
    f = finding(
        ctx,
        rid,
        p,
        c["start"],
        c["end"],
        message,
        fix=FixSpec("replace_text", p.idx, c["start"], c["end"], text=j.suggestion)
        if j.suggestion
        else None,
        severity="warning",
        suggestion=j.suggestion,
        confidence=j.confidence,
        llm_reason=j.reason,
        llm_category=j.category,
    )
    f.source = "llm"
    f.llm_model = j.model
    return f


@rule("VRB-01")
def must_external(doc: KSDoc, ctx: RuleContext):
    js = _judgments(doc, ctx)
    for c in _candidates(doc, ctx):
        if "VRB-01" not in c["kinds"]:
            continue
        p = doc.paras[c["para"]]
        j = js.get(c["id"])
        if j is not None and j.category == "외적 제약":
            continue  # 법령 등 외적 제약 → 적합
        if j is not None and j.category in ("요구사항", "권고사항") and j.suggestion:
            yield _llm_finding(
                ctx, "VRB-01", p, c, j,
                f"AI 판정: {j.category}입니다. 외적 제약이 아니므로 '반드시'를 쓰지 않습니다. {j.reason}".strip(),
            )  # fmt: skip
            continue
        m = MUST_RE.search(c["text"])
        a, b = c["start"] + m.start(), c["start"] + m.end()
        yield finding(
            ctx,
            "VRB-01",
            p,
            a,
            b,
            "'반드시 ~하여야 한다'는 법령 등 문서 밖의 의무(외적 제약)에만 씁니다. "
            "이 표준의 요구사항이면 '반드시'를 뺍니다.",
            fix=FixSpec("replace_text", p.idx, a, b, text="", auto=False),
            suggestion=(c["text"][: m.start()] + c["text"][m.end() :]).strip(),
            confidence=0.7,
        )


@rule("VRB-02")
def can_permission(doc: KSDoc, ctx: RuleContext):
    js = _judgments(doc, ctx)
    for c in _candidates(doc, ctx):
        if "VRB-02" not in c["kinds"]:
            continue
        p = doc.paras[c["para"]]
        j = js.get(c["id"])
        if j is not None and j.category in (
            "가능성/역량",
            "설명",
            "요구사항",
            "권고사항",
            "외적 제약",
        ):
            continue  # '할 수 있다'가 허용 의미가 아님 → 이 규칙 대상 아님
        if j is not None and j.category == "허용":
            msg = "AI 판정: 허용의 뜻이므로 '~해도 된다'로 씁니다(부속서 I 표 I.3)."
            if j.reason:
                msg += f" 근거: {j.reason}"
            if j.rejected:
                msg += f" (AI가 고친 문장은 검증을 통과하지 못해 쓰지 않았습니다: {j.rejected})"
            yield _llm_finding(ctx, "VRB-02", p, c, j, msg)
            continue
        m = CAN_RE.search(c["text"])
        yield finding(
            ctx,
            "VRB-02",
            p,
            c["start"] + m.start(),
            c["start"] + m.end(),
            f"'{m.group()}'이(가) 허용(…해도 된다)의 뜻인지 가능성·역량(…할 수 있다)의 뜻인지 확인이 필요합니다.",
            severity="info",
            confidence=0.5,
            needs_judgement=True,
            llm_status=None if j is None else (j.rejected or "판단보류"),
        )


@rule("VRB-04")
def forbid_form(doc: KSDoc, ctx: RuleContext):
    for p in doc.paras:
        if p.role not in VERB_ROLES | NOTE_ROLES:
            continue
        for m in FORBID_RE.finditer(p.text):
            yield finding(
                ctx,
                "VRB-04",
                p,
                m.start(),
                m.end(),
                f"금지는 '~하여서는 안 된다'로 씁니다('{m.group()}').",
                fix=None,
                suggestion="~하여서는 안 된다",
            )
