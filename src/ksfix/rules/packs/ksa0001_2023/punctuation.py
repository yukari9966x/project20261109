"""문장부호·표기 규칙: PUN-02(연속부호)."""

from __future__ import annotations

import re

from ksfix.model.ir import KSDoc, Role
from ksfix.rules.base import FixSpec
from ksfix.rules.context import RuleContext
from ksfix.rules.packs.ksa0001_2023.common import finding, in_spans, target_paras, url_spans
from ksfix.rules.registry import rule

RANGE_MARK = "∼"  # ∼ TILDE OPERATOR
WRONG_TILDE_RE = re.compile(r"[~～〜]")


@rule("PUN-02")
def range_mark(doc: KSDoc, ctx: RuleContext):
    for p in target_paras(doc, ctx, "PUN-02"):
        urls = url_spans(p.text)
        for m in WRONG_TILDE_RE.finditer(p.text):
            pos = m.start()
            if in_spans(pos, urls):
                continue
            prev = p.text[pos - 1 : pos]
            nxt = p.text[pos + 1 : pos + 2]
            if prev == "/" or nxt == "/":
                continue  # 경로 표기
            yield finding(
                ctx,
                "PUN-02",
                p,
                pos,
                pos + 1,
                f"연속부호는 '∼'(U+223C)를 씁니다('{m.group()}' → '∼').",
                fix=FixSpec("replace_text", p.idx, pos, pos + 1, text=RANGE_MARK),
                suggestion=RANGE_MARK,
            )


SKIP_ROLES = {
    Role.BACK_COVER,
    Role.COVER,
    Role.COVER_INFO,
    Role.TOC_ENTRY,
    Role.TOC_TITLE,
    Role.FORMULA,
    Role.EMPTY,
}


@rule("PUN-01")
def semicolon(doc: KSDoc, ctx: RuleContext):
    for p in doc.paras:
        if p.role in SKIP_ROLES or p.role in (Role.NORMREF_ENTRY, Role.BIBLIO_ENTRY):
            continue
        urls = url_spans(p.text)
        for m in re.finditer(r";", p.text):
            if in_spans(m.start(), urls):
                continue
            yield finding(
                ctx,
                "PUN-01",
                p,
                m.start(),
                m.end(),
                "반쌍점(;)은 쓰지 않습니다. 문장을 나누거나 쉼표를 씁니다.",
            )


DOUBLE_DOT_RE = re.compile(r"(?<![.…])\.\.(?![.…])")
SPACE_BEFORE_RE = re.compile(r"(?<=[가-힣A-Za-z0-9)\]])[  ]+(?=[.,](?:\s|$))")
DOUBLE_SPACE_RE = re.compile(r"(?<=\S) {2,}(?=\S)")
LABEL_PREFIX_RE = re.compile(r"^\s*(?:비\s?고|보\s?기|참\s?고)(?:\s*\d{1,2})?(?=\s)")
PUN06_ROLES = {
    Role.BODY,
    Role.LIST_ITEM,
    Role.NOTE,
    Role.EXAMPLE,
    Role.REMARK,
    Role.DEFINITION,
    Role.FOREWORD,
    Role.INTRO,
    Role.COMMENTARY,
}


@rule("PUN-06")
def punctuation_spacing(doc: KSDoc, ctx: RuleContext):
    for p in doc.paras:
        if p.role not in PUN06_ROLES:
            continue
        urls = url_spans(p.text)
        for m in DOUBLE_DOT_RE.finditer(p.text):
            if in_spans(m.start(), urls):
                continue
            yield finding(
                ctx, "PUN-06", p, m.start(), m.end(), "마침표가 두 번 찍혀 있습니다.",
                fix=FixSpec("replace_text", p.idx, m.start(), m.end(), text="."), suggestion=".",
            )  # fmt: skip
        for m in SPACE_BEFORE_RE.finditer(p.text):
            yield finding(
                ctx, "PUN-06", p, m.start(), m.end() + 1, "문장부호 앞에는 띄우지 않습니다.",
                fix=FixSpec("replace_text", p.idx, m.start(), m.end(), text=""),
                suggestion=p.text[m.end() : m.end() + 1],
            )  # fmt: skip
        label = LABEL_PREFIX_RE.match(p.text)
        for m in DOUBLE_SPACE_RE.finditer(p.text):
            if in_spans(m.start(), urls) or (label and m.start() <= label.end()):
                continue
            yield finding(
                ctx, "PUN-06", p, m.start(), m.end(), "띄어쓰기가 두 칸 이상입니다.",
                fix=FixSpec("replace_text", p.idx, m.start(), m.end(), text=" "), suggestion="한 칸",
            )  # fmt: skip
