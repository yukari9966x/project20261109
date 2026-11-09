"""비고·보기 규칙: NTE-01(라벨과 번호 — 같은 절·표 안에 둘 이상일 때만 번호)."""

from __future__ import annotations

import re

from ksfix.model.ir import KSDoc, Para, Role
from ksfix.rules.base import FixSpec
from ksfix.rules.context import RuleContext
from ksfix.rules.packs.ksa0001_2023.common import finding
from ksfix.rules.registry import rule

WORD = {Role.NOTE: "비고", Role.EXAMPLE: "보기"}
# 라벨 번호는 20 이하, 뒤에 단위·소수점이 오면 내용의 수치("비고  25 ℃의 …")다.
_NUM = r"(\s*(?P<n>[1-9]|1\d|20)(?![\d.,])(?!\s*(?:℃|°|%|mm|cm|m\b|kg|g\b|V\b|A\b|Hz|kHz|MHz|s\b|h\b|min|K\b|N\b|Pa|kPa|MPa|μ|µ|Ω)))?"
LABEL_RE = {
    Role.NOTE: re.compile(r"^(비\s?고)" + _NUM),
    Role.EXAMPLE: re.compile(r"^(보\s?기)" + _NUM),
}


def _label(p: Para) -> tuple[str | None, int | None, bool]:
    """(라벨 숫자 문자열, 숫자, 자동번호 여부)."""
    if p.num_label:
        m = re.fullmatch(r"(?:비\s?고|보\s?기)\s*(\d+)?", p.num_label)
        if m:
            return m.group(1), int(m.group(1)) if m.group(1) else None, True
    m = LABEL_RE[p.role].match(p.text.lstrip())
    if m:
        return m.group("n"), int(m.group("n")) if m.group("n") else None, False
    return None, None, False


@rule("NTE-01")
def note_labels(doc: KSDoc, ctx: RuleContext):
    groups: dict[tuple, list[Para]] = {}
    term = None  # 용어와 정의 절에서는 용어 항목마다 따로 센다
    for p in doc.paras:
        if p.role in (Role.TERM, Role.TERM_NUMBER):
            term = p.attrs.get("number") or p.idx
        elif p.role == Role.HEADING:
            term = None
        if p.role not in WORD:
            continue
        num, _, _ = _label(p)
        if num is None and not p.num_label and not LABEL_RE[p.role].match(p.text.lstrip()):
            continue  # 라벨만 있는 앞 문단에 이어지는 내용
        key = (p.role, p.clause_no, term, p.table_idx if p.in_table else None, p.attrs.get("zone"))
        groups.setdefault(key, []).append(p)
    for (role, *_), items in groups.items():
        word = WORD[role]
        many = len(items) > 1
        for i, p in enumerate(items, start=1):
            num, n, auto = _label(p)
            want = f"{word} {i}" if many else word
            have = f"{word} {n}" if n is not None else word
            if have == want:
                continue
            lead = len(p.text) - len(p.text.lstrip())
            m = LABEL_RE[role].match(p.text.lstrip())
            fix = None
            if not auto and m:
                fix = FixSpec(
                    "replace_text", p.idx, lead, lead + len(m.group(0).rstrip()), text=want
                )
            reason = (
                f"같은 곳에 {word}가 하나뿐이면 번호를 붙이지 않습니다('{have}' → '{word}')."
                if not many
                else f"같은 곳에 {word}가 둘 이상이면 '{word} 1', '{word} 2'처럼 번호를 붙입니다('{have}' → '{want}')."
            )
            yield finding(
                ctx,
                "NTE-01",
                p,
                lead,
                lead + (m.end() if m else 0),
                reason,
                fix=fix,
                suggestion=want,
            )
