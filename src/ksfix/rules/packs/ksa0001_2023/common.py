"""규칙팩 공용 도우미."""

from __future__ import annotations

import difflib
import re

from ksfix.classify import patterns as pt
from ksfix.model.ir import KSDoc, Para, Role
from ksfix.rules.base import Finding, FixSpec, paras_for, snippet
from ksfix.rules.context import RuleContext

URL_RE = re.compile(r"(?:https?://|www\.)\S+|\S+@\S+\.\S+")


def finding(
    ctx: RuleContext,
    rid: str,
    p: Para,
    start: int | None,
    end: int | None,
    message: str | None = None,
    *,
    fix: FixSpec | None = None,
    severity: str | None = None,
    suggestion: str | None = None,
    confidence: float = 1.0,
    **extra,
) -> Finding:
    meta = ctx.meta.get(rid, {})
    return Finding(
        rule_id=rid,
        severity=severity or meta.get("severity", "warning"),
        message=message or meta.get("message") or meta.get("title", rid),
        clause_ref=f"KS A 0001:2023 {meta.get('clause', '')}".strip(),
        block=p.idx,
        start=start,
        end=end,
        snippet=snippet(p.text, start, end),
        fix=fix,
        suggestion=suggestion,
        confidence=confidence,
        extra=extra,
    )


def applies(ctx: RuleContext, rid: str, default: list[str] | None = None) -> list[Role] | None:
    roles = ctx.meta.get(rid, {}).get("applies_to") or default
    return [Role(r) for r in roles] if roles else None


def target_paras(
    doc: KSDoc, ctx: RuleContext, rid: str, default: list[str] | None = None
) -> list[Para]:
    return paras_for(doc, applies(ctx, rid, default))


def url_spans(text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in URL_RE.finditer(text)]


def in_spans(pos: int, spans: list[tuple[int, int]]) -> bool:
    return any(a <= pos < b for a, b in spans)


def similarity(a: str, b: str) -> float:
    """공백·문장부호 정규화 후 SequenceMatcher 비율."""
    na = re.sub(r"[\s.,·ㆍ“”\"'()]", "", a)
    nb = re.sub(r"[\s.,·ㆍ“”\"'()]", "", b)
    if not na and not nb:
        return 1.0
    return difflib.SequenceMatcher(None, na, nb, autojunk=False).ratio()


def same_text(a: str, b: str) -> bool:
    return pt.squash(a) == pt.squash(b)


def clause_paras(doc: KSDoc, heading: Para) -> list[Para]:
    """1단계 절 제목 뒤부터 다음 1단계 절/부속서 전까지의 문단(표 안 포함)."""
    out = []
    for q in doc.paras[heading.idx + 1 :]:
        if q.role == Role.HEADING and (q.attrs.get("level") or 1) == 1:
            break
        if q.role in (Role.ANNEX_HEADING, Role.BIBLIO_TITLE, Role.COMMENTARY_TITLE):
            break
        if q.attrs.get("zone") not in ("body",):
            break
        out.append(q)
    return out


def first_clause(doc: KSDoc, kind: str) -> Para | None:
    for p in doc.paras:
        if (
            p.role == Role.HEADING
            and (p.attrs.get("level") or 1) == 1
            and p.attrs.get("zone") == "body"
            and p.attrs.get("clause_kind") == kind
        ):
            return p
    return None


def unit_alternation(units: list[str]) -> str:
    return "|".join(re.escape(u) for u in sorted(set(units), key=len, reverse=True))
