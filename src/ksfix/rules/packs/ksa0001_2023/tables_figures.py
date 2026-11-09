"""표·그림 규칙: TBL-01·FIG-01(꼴), TBL-02·FIG-02(위치), TBL-03(표 안의 표), TBL-04·FIG-03(본문 참조)."""

from __future__ import annotations

import re

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


def _prev_nonempty(doc: KSDoc, idx: int):
    for q in reversed(doc.paras[:idx]):
        if q.role != Role.EMPTY:
            return q
    return None


def _next_nonempty(doc: KSDoc, idx: int):
    for q in doc.paras[idx + 1 :]:
        if q.role != Role.EMPTY:
            return q
    return None


def _center_fix(p) -> FixSpec | None:
    if p.attrs.get("jc") in ("center",):
        return None
    return FixSpec("set_alignment", p.idx, props={"jc": "center"})


CONTENT_ZONES = {"body", "annex", "commentary"}


@rule("TBL-02")
def table_caption_position(doc: KSDoc, ctx: RuleContext):
    for t in doc.tables:
        if t.in_table or not t.paras:
            continue
        first, last = t.paras[0], t.paras[-1]
        if first.attrs.get("zone") not in CONTENT_ZONES:
            continue
        before = _prev_nonempty(doc, first.idx)
        unit = None
        if before is not None and before.role == Role.UNIT_LABEL:
            unit, before = before, _prev_nonempty(doc, before.idx)
        after = _next_nonempty(doc, last.idx)
        if before is not None and before.role == Role.TABLE_CAPTION and not before.in_table:
            fx = _center_fix(before)
            if fx is not None:
                yield finding(
                    ctx, "TBL-02", before, None, None, "표 제목은 가운데에 둡니다.", fix=fx
                )
            continue
        if after is not None and after.role == Role.TABLE_CAPTION and not after.in_table:
            target = unit if unit is not None else None
            props = {"where": "before"}
            if target is not None:
                props["to"] = target.idx
            else:
                props["to_table"] = t.idx
            yield finding(
                ctx,
                "TBL-02",
                after,
                None,
                None,
                "표 제목은 표 위에 둡니다(지금은 표 아래에 있음).",
                fix=FixSpec("move_paragraph", after.idx, props=props),
                suggestion="표 위로 옮김",
            )


FIG_BETWEEN = {Role.NOTE, Role.EXAMPLE, Role.REMARK, Role.FIGURE, Role.UNIT_LABEL, Role.TABLE_CELL}


@rule("FIG-02")
def figure_caption_position(doc: KSDoc, ctx: RuleContext):
    for p in doc.by_role(Role.FIGURE):
        if p.in_table or p.attrs.get("zone") not in CONTENT_ZONES:
            continue
        after = _next_nonempty(doc, p.idx)
        while after is not None and after.role in FIG_BETWEEN:
            after = _next_nonempty(doc, after.idx)  # 그림 비고·여러 그림 조각 건너뜀
        before = _prev_nonempty(doc, p.idx)
        if before is not None and before.role == Role.FIGURE_CAPTION:
            above = _prev_nonempty(doc, before.idx)
            if above is not None and above.role == Role.FIGURE:
                before = None  # 다른 그림의 제목(그 그림 바로 아래)
        if after is not None and after.role == Role.FIGURE_CAPTION:
            fx = _center_fix(after)
            if fx is not None:
                yield finding(
                    ctx, "FIG-02", after, None, None, "그림 제목은 가운데에 둡니다.", fix=fx
                )
            continue
        if before is not None and before.role == Role.FIGURE_CAPTION:
            yield finding(
                ctx,
                "FIG-02",
                before,
                None,
                None,
                "그림 제목은 그림 아래에 둡니다(지금은 그림 위에 있음).",
                fix=FixSpec("move_paragraph", before.idx, props={"to": p.idx, "where": "after"}),
                suggestion="그림 아래로 옮김",
            )


@rule("TBL-03")
def nested_tables(doc: KSDoc, ctx: RuleContext):
    for t in doc.tables:
        if t.in_table and t.paras:
            yield finding(ctx, "TBL-03", t.paras[0], None, None, "표 안에 표를 넣지 않습니다.")


REF_TEXT_ROLES = {
    Role.BODY, Role.LIST_ITEM, Role.NOTE, Role.EXAMPLE, Role.REMARK, Role.DEFINITION,
    Role.TABLE_CELL, Role.UNIT_LABEL, Role.COMMENTARY,
}  # fmt: skip


def _referenced(doc: KSDoc, word: str, num: str) -> bool:
    pat = re.compile(rf"(?<![\w]){word}\s*{re.escape(num)}(?![\d.]*\d)")
    return any(p.role in REF_TEXT_ROLES and pat.search(p.text) for p in doc.paras)


def _unreferenced(doc: KSDoc, ctx: RuleContext, rid: str, role: Role, word: str):
    seen: set[str] = set()
    for p in doc.by_role(role):
        m = pt.CAPTION_RE.match(p.text.strip())
        if not m or "(계속)" in p.text:
            continue
        num = m.group("num")
        if num in seen:
            continue
        seen.add(num)
        if not _referenced(doc, word, num):
            yield finding(
                ctx, rid, p, None, None, f"{word} {num}을(를) 본문에서 참조하지 않습니다."
            )


@rule("TBL-04")
def tables_referenced(doc: KSDoc, ctx: RuleContext):
    yield from _unreferenced(doc, ctx, "TBL-04", Role.TABLE_CAPTION, "표")


@rule("FIG-03")
def figures_referenced(doc: KSDoc, ctx: RuleContext):
    yield from _unreferenced(doc, ctx, "FIG-03", Role.FIGURE_CAPTION, "그림")
