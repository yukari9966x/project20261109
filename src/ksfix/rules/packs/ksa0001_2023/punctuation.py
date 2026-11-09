"""문장부호·표기 규칙: PUN-02(연속부호)."""

from __future__ import annotations

import re

from ksfix.model.ir import KSDoc
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
