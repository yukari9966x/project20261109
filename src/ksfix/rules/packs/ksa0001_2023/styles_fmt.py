"""KSDT 서식 규칙: FMT-01(역할별 KSDT 스타일 — 표·그림 제목)."""

from __future__ import annotations

from ksfix.model.ir import KSDoc, Role
from ksfix.rules.base import FixSpec
from ksfix.rules.context import RuleContext
from ksfix.rules.packs.ksa0001_2023.common import finding
from ksfix.rules.registry import rule

WANT = {
    Role.TABLE_CAPTION: ("[KSDT] 표제목", ("표제목",)),
    Role.FIGURE_CAPTION: ("[KSDT] 그림제목", ("그림제목", "부도제목")),
}


@rule("FMT-01")
def ksdt_styles(doc: KSDoc, ctx: RuleContext):
    has_ksdt = doc.styles is not None and any(
        (s.name or "").startswith("[KSDT]") for s in doc.styles.styles.values()
    )
    for role, (style_name, needles) in WANT.items():
        sid = doc.styles.find_by_name(style_name) if doc.styles is not None else None
        for p in doc.by_role(role):
            chain = p.attrs.get("style_chain") or []
            if any(n in name for name in chain for n in needles):
                continue
            if p.in_table:
                continue
            what = "표 제목" if role == Role.TABLE_CAPTION else "그림 제목"
            if sid is None:
                if not has_ksdt:
                    continue  # KSDT 스타일이 없는 문서는 문서 단위 안내만(리포트 경고)
                fix = None
            else:
                fix = FixSpec("set_style", p.idx, style=style_name)
            yield finding(
                ctx,
                "FMT-01",
                p,
                None,
                None,
                f"{what}에는 KSDT 스타일 '{style_name}'을(를) 씁니다(지금: {p.style_name or '없음'}).",
                fix=fix,
                suggestion=style_name,
            )
