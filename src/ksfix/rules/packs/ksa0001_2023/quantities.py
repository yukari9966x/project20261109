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


QTY_ROLES = [
    "body",
    "list_item",
    "note",
    "example",
    "remark",
    "definition",
    "table_cell",
    "commentary",
    "intro",
]
LEAD_DOT_RE = re.compile(r"(?<![\w.,)])\.(\d+)")
DEC_COMMA_RE = re.compile(r"(?<![\w.,])(\d+),(\d{1,2}|\d{4,})(?![\d,])")


@rule("QTY-02")
def decimal_marker(doc: KSDoc, ctx: RuleContext):
    for p in target_paras(doc, ctx, "QTY-02", QTY_ROLES):
        urls = url_spans(p.text)
        for m in LEAD_DOT_RE.finditer(p.text):
            if in_spans(m.start(), urls):
                continue
            yield finding(
                ctx,
                "QTY-02",
                p,
                m.start(),
                m.end(),
                f"1보다 작은 소수는 앞에 0을 씁니다('{m.group()}' → '0{m.group()}').",
                fix=FixSpec("replace_text", p.idx, m.start(), m.start(), text="0"),
                suggestion=f"0{m.group()}",
            )
        for m in DEC_COMMA_RE.finditer(p.text):
            yield finding(
                ctx,
                "QTY-02",
                p,
                m.start(),
                m.end(),
                f"소수점은 마침표를 씁니다('{m.group()}' → '{m.group(1)}.{m.group(2)}'). 천 단위 구분이면 공백으로 묶습니다.",
                fix=FixSpec(
                    "replace_text",
                    p.idx,
                    m.start(1) + len(m.group(1)),
                    m.start(2),
                    text=".",
                    auto=False,
                ),
                suggestion=f"{m.group(1)}.{m.group(2)}",
                severity="info",
            )


@cache
def _qty03_re(units: tuple[str, ...]) -> re.Pattern[str]:
    return re.compile(
        rf"(?<![\w.,\-])(?P<num>\d{{1,3}}(?:,\d{{3}})+|\d{{4,}})(?![\d,.])(?P<sp>[  ]*)"
        rf"(?P<unit>{unit_alternation(list(units))}){UNIT_RIGHT}"
    )


def _group(digits: str) -> str:
    digits = digits.replace(",", "")
    parts = []
    while len(digits) > 3:
        parts.insert(0, digits[-3:])
        digits = digits[:-3]
    parts.insert(0, digits)
    return " ".join(parts)


@rule("QTY-03")
def digit_grouping(doc: KSDoc, ctx: RuleContext):
    auto, sugg = all_units(ctx)
    regex = _qty03_re(tuple(auto + sugg))
    for p in target_paras(doc, ctx, "QTY-03", QTY_ROLES):
        for m in regex.finditer(p.text):
            num = m.group("num")
            if re.fullmatch(r"(?:19|20)\d\d", num):
                continue  # 연도
            want = _group(num)
            if want == num:
                continue
            yield finding(
                ctx,
                "QTY-03",
                p,
                m.start("num"),
                m.end("num"),
                f"세 자리마다 공백으로 묶습니다('{num}' → '{want}').",
                fix=FixSpec("replace_text", p.idx, m.start("num"), m.end("num"), text=want),
                suggestion=want,
            )


@cache
def _qty05_re(units: tuple[str, ...]) -> re.Pattern[str]:
    alt = unit_alternation(list(units))
    return re.compile(
        rf"(?<![(\d.,])(?P<a>{NUM})(?![\d.,])[  ]*(?P<sep>[∼~～〜－–])[  ]*(?P<b>{NUM})"
        rf"(?P<sp>[  ]*)(?P<unit>{alt}){UNIT_RIGHT}"
    )


@rule("QTY-05")
def range_units(doc: KSDoc, ctx: RuleContext):
    auto, sugg = all_units(ctx)
    regex = _qty05_re(tuple(auto + sugg))
    for p in target_paras(doc, ctx, "QTY-05", QTY_ROLES):
        for m in regex.finditer(p.text):
            unit = m.group("unit")
            new = f"{m.group('a')} {unit} ∼ {m.group('b')} {unit}"
            yield finding(
                ctx,
                "QTY-05",
                p,
                m.start(),
                m.end(),
                f"범위는 수치마다 단위를 붙입니다('{m.group()}' → '{new}'). '({m.group('a')} ∼ {m.group('b')}) {unit}'도 됩니다.",
                fix=FixSpec("replace_text", p.idx, m.start(), m.end(), text=new),
                suggestion=new,
            )


@cache
def _qty06_re(units: tuple[str, ...]) -> re.Pattern[str]:
    alt = unit_alternation(list(units))
    return re.compile(rf"(?<=\d)(?:[  ]*(?:{alt}))?[  ]+(?P<x>[xX*])[  ]+(?=\d)")


@rule("QTY-06")
def multiplication_sign(doc: KSDoc, ctx: RuleContext):
    auto, sugg = all_units(ctx)
    regex = _qty06_re(tuple(auto + sugg))
    for p in target_paras(doc, ctx, "QTY-06", QTY_ROLES):
        for m in regex.finditer(p.text):
            a, b = m.start("x"), m.end("x")
            yield finding(
                ctx,
                "QTY-06",
                p,
                a,
                b,
                f"곱셈 기호는 '×'를 씁니다('{m.group('x')}' → '×').",
                fix=FixSpec("replace_text", p.idx, a, b, text="×"),
                suggestion="×",
            )
