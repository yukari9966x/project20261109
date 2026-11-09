"""용어와 정의 규칙: TRM-01(용어 꼴), TRM-02(정의문 끝 마침표)."""

from __future__ import annotations

import re

from ksfix.model.ir import KSDoc, Role
from ksfix.rules.base import FixSpec
from ksfix.rules.context import RuleContext
from ksfix.rules.packs.ksa0001_2023.common import finding
from ksfix.rules.registry import rule

TERM_RE = re.compile(r"(?P<ko>[^()\n]*?[가-힣][^()\n]*?)(?P<sp>\s+)?\((?P<en>[^()]+)\)\s*$")


@rule("TRM-01")
def term_form(doc: KSDoc, ctx: RuleContext):
    for p in doc.by_role(Role.TERM):
        m = TERM_RE.search(p.text)
        if not m:
            continue
        if m.group("sp"):
            yield finding(
                ctx,
                "TRM-01",
                p,
                m.start("sp"),
                m.end("sp") + 1,
                "용어와 괄호 사이를 띄우지 않습니다(예: 최대 칭량(maximum capacity)).",
                fix=FixSpec("replace_text", p.idx, m.start("sp"), m.end("sp"), text=""),
                suggestion=f"{m.group('ko').strip()}({m.group('en')})",
            )
        en = m.group("en").strip()
        if re.match(r"[A-Z][a-z]", en) and not re.match(r"[A-Z][a-z]+\s+[A-Z]", en):
            yield finding(
                ctx,
                "TRM-01",
                p,
                m.start("en"),
                m.end("en"),
                "영문 용어는 고유명사가 아니면 소문자로 시작합니다.",
                fix=FixSpec(
                    "replace_text",
                    p.idx,
                    m.start("en"),
                    m.start("en") + 1,
                    text=en[0].lower(),
                    auto=False,
                ),
                suggestion=en[0].lower() + en[1:],
            )


@rule("TRM-02")
def definition_period(doc: KSDoc, ctx: RuleContext):
    for p in doc.by_role(Role.DEFINITION):
        text = p.text.rstrip()
        if text.endswith(".") and not text.endswith(".."):
            pos = len(text) - 1
            yield finding(
                ctx,
                "TRM-02",
                p,
                pos,
                pos + 1,
                "정의문 끝에는 마침표를 찍지 않습니다.",
                fix=FixSpec("replace_text", p.idx, pos, pos + 1, text=""),
                suggestion=text[:-1],
            )
