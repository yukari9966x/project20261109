"""숫자·단위 규칙: QTY-01(수치와 단위 띄어쓰기), QTY-04(허용오차 괄호)."""

from __future__ import annotations

import re
from functools import cache

from ksfix.model.ir import KSDoc
from ksfix.rules.base import FixSpec
from ksfix.rules.context import RuleContext
from ksfix.rules.packs.ksa0001_2023.common import (
    finding,
    in_spans,
    target_paras,
    unit_alternation,
    url_spans,
)
from ksfix.rules.registry import rule

NUM = r"\d+(?:[.,]\d+)*"
# 수치 앞: 글자·숫자·소수점·붙임표 등이 붙어 있으면 수치가 아니다(M8, IP65, 60974-1 …)
NUM_LEFT = r"(?<![\w.,/:\-±])"
UNIT_RIGHT = r"(?![A-Za-z0-9µμΩ²³·/°])"


def all_units(ctx: RuleContext) -> tuple[list[str], list[str]]:
    auto = list(ctx.p("QTY-01", "auto_units", []))
    sugg = list(ctx.p("QTY-01", "suggest_only_units", []))
    return auto, sugg


@cache
def _qty01_re(auto: tuple[str, ...], sugg: tuple[str, ...]) -> re.Pattern[str]:
    return re.compile(
        rf"{NUM_LEFT}(?P<num>{NUM})(?P<unit>{unit_alternation(list(auto) + list(sugg))}){UNIT_RIGHT}"
    )


CODE_WORDS_RE = re.compile(
    r"(?:그룹|등급|클래스|부류|범주|형식|유형|하위분류|종류|품종|코드|기호|모델|번)\s*$"
)
CODE_TOKEN_RE = re.compile(r"(?<![\w.])\d+[A-Z](?![\w])")


def code_like(text: str, m: re.Match[str]) -> bool:
    """'2C', '그룹 1A', '2B, 2C, 2R'처럼 숫자+대문자 코드로 보이면 True."""
    if m.group().strip() == text.strip():
        return True
    if CODE_WORDS_RE.search(text[: m.start()]):
        return True
    return len(CODE_TOKEN_RE.findall(text)) >= 2


@rule("QTY-01")
def number_unit_space(doc: KSDoc, ctx: RuleContext):
    auto, sugg = all_units(ctx)
    regex = _qty01_re(tuple(auto), tuple(sugg))
    space = ctx.p("QTY-01", "space_char", " ")
    auto_set = set(auto)
    for p in target_paras(doc, ctx, "QTY-01"):
        urls = url_spans(p.text)
        for m in regex.finditer(p.text):
            if in_spans(m.start(), urls):
                continue
            unit = m.group("unit")
            pos = m.end("num")
            is_auto = unit in auto_set
            if not is_auto and code_like(p.text, m):
                continue
            yield finding(
                ctx,
                "QTY-01",
                p,
                m.start(),
                m.end(),
                f"수치와 단위기호 사이를 한 칸 띄웁니다('{m.group()}' → '{m.group('num')} {unit}')."
                + ("" if is_auto else " 한 글자 단위는 다른 뜻일 수 있어 제안만 합니다."),
                fix=FixSpec("replace_text", p.idx, pos, pos, text=space, auto=is_auto),
                severity=None if is_auto else "info",
                suggestion=f"{m.group('num')} {unit}",
                confidence=1.0 if is_auto else 0.5,
            )


@cache
def _qty04_re(units: tuple[str, ...]) -> re.Pattern[str]:
    return re.compile(
        rf"(?<![(\d.,])(?P<a>{NUM})\s*±\s*(?P<b>{NUM})(?P<sp>[  ]*)(?P<unit>{unit_alternation(list(units))}){UNIT_RIGHT}"
    )


@rule("QTY-04")
def tolerance_parens(doc: KSDoc, ctx: RuleContext):
    auto, sugg = all_units(ctx)
    regex = _qty04_re(tuple(auto + sugg))
    for p in target_paras(doc, ctx, "QTY-04"):
        for m in regex.finditer(p.text):
            before = p.text[: m.start()].rstrip()
            if before.endswith("("):
                continue
            new = f"({m.group('a')} ± {m.group('b')}) {m.group('unit')}"
            yield finding(
                ctx,
                "QTY-04",
                p,
                m.start(),
                m.end(),
                f"허용오차가 있는 값은 괄호로 묶고 단위를 뒤에 씁니다('{m.group()}' → '{new}').",
                fix=FixSpec("replace_text", p.idx, m.start(), m.end(), text=new),
                suggestion=new,
            )
