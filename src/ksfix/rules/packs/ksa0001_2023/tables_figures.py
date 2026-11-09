"""표·그림 규칙: TBL-01·FIG-01(호칭과 제목 꼴)."""

from __future__ import annotations

from ksfix.classify import patterns as pt
from ksfix.model.ir import KSDoc, Para, Role
from ksfix.rules.base import FixSpec
from ksfix.rules.context import RuleContext
from ksfix.rules.packs.ksa0001_2023.common import finding
from ksfix.rules.registry import rule

EM_DASH = "—"


def expected_caption(p: Para) -> tuple[int, int, str, str] | None:
    """(시작, 끝, 기대 문자열, 종류) — 캡션 꼴이 아니면 None."""
    text = p.text
    lead = len(text) - len(text.lstrip())
    stripped = text.strip()
    m = pt.CAPTION_RE.match(stripped)
    if not m:
        return None
    kind = m.group("kind")
    title = m.group("rest").strip()
    title = title.lstrip(f" {EM_DASH}–-:.．\t").strip()
    want = f"{kind} {m.group('num')} {EM_DASH} {title}" if title else f"{kind} {m.group('num')}"
    return lead, lead + len(stripped), want, kind


def _check(doc: KSDoc, ctx: RuleContext, rid: str, role: Role, word: str):
    for p in doc.by_role(role):
        exp = expected_caption(p)
        if exp is None:
            continue
        start, end, want, kind = exp
        if kind != word:
            continue
        have = p.text[start:end]
        if have == want:
            continue
        yield finding(
            ctx,
            rid,
            p,
            start,
            end,
            f"{word} 호칭과 제목은 '{word} N — 제목'처럼 줄표(—) 앞뒤를 한 칸씩 띄워 씁니다.",
            fix=FixSpec("replace_text", p.idx, start, end, text=want),
            suggestion=want,
        )


@rule("TBL-01")
def table_caption_form(doc: KSDoc, ctx: RuleContext):
    yield from _check(doc, ctx, "TBL-01", Role.TABLE_CAPTION, "표")


@rule("FIG-01")
def figure_caption_form(doc: KSDoc, ctx: RuleContext):
    yield from _check(doc, ctx, "FIG-01", Role.FIGURE_CAPTION, "그림")
