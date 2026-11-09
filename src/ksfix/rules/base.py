"""규칙 엔진 기본 타입: 지적(Finding)과 수정안(FixSpec)."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Literal, Protocol

from ksfix.model.ir import KSDoc, Para, Role

if TYPE_CHECKING:
    from ksfix.rules.context import RuleContext

Severity = Literal["error", "warning", "info"]
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}

FixKind = Literal[
    "replace_text",
    "set_style",
    "insert_paragraph_before",
    "insert_paragraph_after",
    "delete_paragraph",
    "move_paragraph",
    "set_run_props",
    "set_alignment",
    "set_table_header",
    "set_doc_setting",
]


@dataclass
class FixSpec:
    kind: FixKind
    target: int  # 문단 idx
    start: int | None = None
    end: int | None = None
    text: str | None = None
    style: str | None = None  # set_style·insert: 스타일 역할 키 또는 이름
    props: dict | None = None
    auto: bool = True  # False면 제안(메모)만


@dataclass
class Finding:
    rule_id: str
    severity: Severity
    message: str  # 한국어, 무엇이 왜 문제인지 한 문장
    clause_ref: str  # 예: "KS A 0001:2023 부속서 L"
    block: int
    start: int | None
    end: int | None
    snippet: str
    fix: FixSpec | None = None
    source: Literal["rule", "llm"] = "rule"
    confidence: float = 1.0
    llm_model: str | None = None
    category: str | None = None
    priority: str | None = None
    title: str | None = None
    suggestion: str | None = None  # 수정 미리보기(사람이 읽는 형태)
    status: str = "open"  # open | fixed | suggested | reverted | skipped
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @property
    def autofixable(self) -> bool:
        return self.fix is not None and self.fix.auto


class RuleFunc(Protocol):
    def __call__(self, doc: KSDoc, ctx: RuleContext) -> Iterable[Finding]: ...


def snippet(text: str, start: int | None, end: int | None, width: int = 24) -> str:
    if start is None or end is None:
        return text[:80]
    a = max(0, start - width)
    b = min(len(text), end + width)
    s = text[a:b].replace("\n", " ").replace("\t", " ")
    return ("…" if a > 0 else "") + s + ("…" if b < len(text) else "")


TEXT_ROLES = {
    Role.BODY,
    Role.LIST_ITEM,
    Role.NOTE,
    Role.EXAMPLE,
    Role.REMARK,
    Role.TABLE_CELL,
    Role.DEFINITION,
    Role.FOREWORD,
    Role.INTRO,
    Role.COMMENTARY,
    Role.UNIT_LABEL,
    Role.TERM_SOURCE,
}


def paras_for(doc: KSDoc, roles: Iterable[Role | str] | None) -> list[Para]:
    if roles is None:
        want = TEXT_ROLES
    else:
        want = {Role(r) if isinstance(r, str) else r for r in roles}
    return [p for p in doc.paras if p.role in want]


def finditer(paras: Iterable[Para], regex: re.Pattern[str]) -> Iterator[tuple[Para, re.Match[str]]]:
    for p in paras:
        for m in regex.finditer(p.text):
            yield p, m
