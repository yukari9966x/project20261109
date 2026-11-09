"""기계 판독용 JSON 리포트(HTML 리포트도 이 dict 하나로 그린다)."""

from __future__ import annotations

import datetime as dt
from collections import Counter
from typing import Any

from ksfix import __version__
from ksfix.model.ir import Para, Role
from ksfix.report.checklist import build_checklist, checklist_summary
from ksfix.rules.registry import load_catalog

ZONE_KO = {
    "foreword": "머리말",
    "intro": "개요",
    "toc": "목차",
    "title": "제목",
    "biblio": "참고문헌",
    "commentary": "해설",
    "cover": "표지",
    "cover_info": "표지",
    "back_cover": "뒤표지",
}
DOC_META_KEYS = (
    "paragraph_count",
    "table_count",
    "sections",
    "hangul_ratio",
    "std_number",
    "title_ko",
    "title_en",
    "adoption",
    "comment_count",
    "has_tracked_changes",
    "has_toc_field",
    "parts",
    "ks_target",
    "low_confidence",
)


def location(p: Para | None) -> str:
    if p is None:
        return ""
    if p.role == Role.HEADING and p.attrs.get("number"):
        return f"{p.attrs['number']} 제목"
    if p.role == Role.ANNEX_HEADING:
        return f"부속서 {p.attrs.get('letter') or ''}".strip()
    where = ZONE_KO.get(p.attrs.get("zone", ""), "")
    if p.clause_no:
        where = f"부속서 {p.clause_no}" if p.clause_no.isalpha() else f"{p.clause_no}절"
        if "." in p.clause_no:
            where = p.clause_no
    if p.in_table and p.table_idx is not None:
        return f"{where} · 표 안".strip(" ·")
    return where


def status_label(f, action: str | None) -> str:
    if action == "apply":
        return "자동수정"
    if f.source == "llm":
        return "AI 제안"
    if f.extra.get("needs_judgement"):
        return "판단 필요"
    if action is None:
        if f.fix is not None and f.fix.auto:
            return "자동수정 가능"
        return "제안" if f.fix is not None else "검토 필요"
    return "제안" if f.fix is not None else "검토 필요"


def build_report(
    check, fix=None, *, source_name: str, input_unchanged: bool | None = None
) -> dict[str, Any]:
    doc = check.doc
    cat = load_catalog()
    decisions = {id(d.finding): d for d in (fix.decisions if fix else [])}
    findings = []
    for f in check.findings:
        p = doc.paras[f.block] if 0 <= f.block < len(doc.paras) else None
        d = decisions.get(id(f))
        action = d.action if d else None
        row = f.to_dict()
        row.update(
            {
                "role": p.role.value if p else None,
                "clause_no": p.clause_no if p else None,
                "location": location(p),
                "action": action,
                "status_label": status_label(f, action),
                "reason": d.reason if d else None,
            }
        )
        findings.append(row)

    before = check.summary()
    summary: dict[str, Any] = {
        "findings": before["findings"],
        "by_severity": before["by_severity"],
        "autofixable": before["autofixable"],
        "needs_review": before["needs_review"],
        "rules_applied": before["rules_applied"],
        "rules_passed": before["rules_passed"],
        "pass_rate_before": before["pass_rate"],
        "pass_rate_after": None,
        "applied": 0,
        "suggested": 0,
        "reported": 0,
        "comments": 0,
        "remaining_autofix": None,
    }
    if fix is not None:
        fs = fix.summary()
        summary.update(
            {
                "pass_rate_after": fs["pass_rate_after"],
                "applied": fs["applied"],
                "suggested": fs["suggested"],
                "reported": fs["reported"],
                "comments": fs["comments"],
                "remaining_autofix": fs["remaining_autofix"],
                "needs_review": fs["suggested"] + fs["reported"],
            }
        )

    by_cat: dict[str, Counter] = {}
    for row in findings:
        c = by_cat.setdefault(row["category"] or "기타", Counter())
        c["count"] += 1
        if row["action"] == "apply":
            c["fixed"] += 1
    categories = [
        {"name": k, "count": v["count"], "fixed": v["fixed"]}
        for k, v in sorted(by_cat.items(), key=lambda kv: -kv[1]["count"])
    ]

    items = build_checklist(check.findings, check.rules)
    return {
        "tool": {"name": "KS-Fix", "version": __version__},
        "generated_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "source": {"name": source_name, "sha256": doc.meta.get("sha256")},
        "mode": fix.mode if fix else "check",
        "rule_pack": {"pack": cat.pack, "version": cat.version, "title": cat.title},
        "llm": {
            "profile": getattr(check, "llm_profile", None) or "none",
            "model": getattr(check, "llm_model", None),
        },
        "summary": summary,
        "categories": categories,
        "warnings": check.warnings,
        "document": {k: doc.meta.get(k) for k in DOC_META_KEYS},
        "findings": findings,
        "checklist": {"items": items, "summary": checklist_summary(items)},
        "verification": {
            "invariants": fix.invariants if fix else None,
            "integrity": fix.integrity if fix else None,
            "input_unchanged": input_unchanged,
        },
        "after": None
        if fix is None or fix.after is None
        else {"summary": fix.after.summary(), "findings": len(fix.after.findings)},
        "diagnostics": check.diagnostics,
        "timings": fix.timings if fix else check.timings,
    }
