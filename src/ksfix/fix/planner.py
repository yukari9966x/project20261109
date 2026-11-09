"""편집 계획: 어떤 지적을 자동 수정하고 어떤 것을 메모(제안)로 남길지 정한다.

- 같은 문단에서 겹치는 편집은 규칙 우선순위(P0 > P0b > P1 > P2) → 심각도 → 넓은 구간 → 규칙 ID 순으로 하나만.
- 수정 금지 구역(필드·기존 변경추적·여러 w:t 런)과 기술적 내용을 바꾸는 편집(INV-01)은 메모로 강등.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ksfix.fix.invariants import text_tokens
from ksfix.fix.textedit import simulate
from ksfix.model.ir import KSDoc
from ksfix.rules.base import Finding

PRIORITY_RANK = {"P0": 0, "P0b": 1, "P1": 2, "P2": 3}
SEVERITY_RANK = {"error": 0, "warning": 1, "info": 2}
TEXT_KINDS = {"replace_text"}
INSERT_KINDS = {"insert_paragraph_after", "insert_paragraph_before"}
PARA_KINDS = {"set_style", "set_alignment", "set_table_header"}
STRUCT_KINDS = {"move_paragraph", "delete_paragraph"}


@dataclass
class Decision:
    finding: Finding
    action: str  # apply | suggest | report
    reason: str | None = None
    covered_by: str | None = None
    anchors: list = field(default_factory=list)


def _rank(f: Finding) -> tuple:
    fx = f.fix
    span = (fx.end - fx.start) if fx and fx.start is not None and fx.end is not None else 0
    return (
        PRIORITY_RANK.get(f.priority or "P1", 2),
        SEVERITY_RANK.get(f.severity, 1),
        -span,
        f.rule_id,
        f.block,
        f.start or 0,
    )


def _overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
    (s1, e1), (s2, e2) = a, b
    if s1 == e1 and s2 == e2:
        return s1 == s2
    if s1 == e1:
        return s2 < s1 < e2
    if s2 == e2:
        return s1 < s2 < e1
    return s1 < e2 and s2 < e1


def plan(
    doc: KSDoc,
    findings: list[Finding],
    mode: str,
    *,
    allow_edits: bool = True,
    apply_llm: bool = False,
    llm_min_conf: float = 0.9,
) -> list[Decision]:
    decisions = {id(f): Decision(f, "report") for f in findings}
    accepted_text: dict[int, list[tuple[int, int, Finding]]] = {}
    para_kinds_used: set[tuple[int, str]] = set()
    struct_used: set[int] = set()

    for f in sorted(findings, key=_rank):
        d = decisions[id(f)]
        fx = f.fix
        if fx is None:
            d.action, d.reason = "report", None
            continue
        d.action = "suggest"
        if mode == "report":
            d.reason = "리포트 모드"
            continue
        if not fx.auto:
            d.reason = "판단이 필요한 수정이라 제안만"
            continue
        if (
            f.source == "llm"
            and mode != "tracked"
            and not (apply_llm and f.confidence >= llm_min_conf)
        ):
            d.reason = "AI 제안은 반영본에 자동 반영하지 않음(메모로만)"
            continue
        if not allow_edits:
            d.reason = "기존 변경추적이 있는 문서라 메모만 남김"
            continue
        if fx.kind in TEXT_KINDS:
            p = doc.paras[fx.target]
            start, end = fx.start or 0, fx.end if fx.end is not None else len(p.text)
            if not p.is_editable(start, end):
                d.reason = "수정 금지 구역(필드·기존 변경추적 등)"
                continue
            clash = next(
                (
                    g
                    for (s, e, g) in accepted_text.get(fx.target, [])
                    if _overlaps((s, e), (start, end))
                ),
                None,
            )
            if clash is not None:
                gfx = clash.fix
                inside = (
                    gfx.start <= start and end <= gfx.end and (fx.text or "") in (gfx.text or "")
                )
                if inside:
                    d.action, d.covered_by = "apply", clash.rule_id
                    d.reason = f"{clash.rule_id} 수정에 포함"
                else:
                    d.reason = f"다른 수정({clash.rule_id})과 겹침"
                continue
            old = p.text
            new = simulate(old, [(start, end, fx.text or "")])
            if text_tokens(old, p.in_table) != text_tokens(new, p.in_table):
                d.reason = "INV-01: 기술적 내용(수치·단위·표준번호)이 바뀌는 수정이라 철회"
                f.extra["inv01"] = True
                continue
            accepted_text.setdefault(fx.target, []).append((start, end, f))
            d.action, d.reason = "apply", None
        elif fx.kind in INSERT_KINDS or fx.kind == "set_doc_setting":
            d.action, d.reason = "apply", None
        elif fx.kind in PARA_KINDS:
            key = (fx.target, fx.kind)
            if key in para_kinds_used or fx.target in struct_used:
                d.reason = "같은 문단의 다른 서식 수정과 겹침"
                continue
            para_kinds_used.add(key)
            d.action, d.reason = "apply", None
        elif fx.kind in STRUCT_KINDS:
            if fx.target in struct_used:
                d.reason = "같은 문단의 다른 이동·삭제와 겹침"
                continue
            struct_used.add(fx.target)
            d.action, d.reason = "apply", None
        else:
            d.reason = f"지원하지 않는 수정 종류: {fx.kind}"
    return [decisions[id(f)] for f in findings]
