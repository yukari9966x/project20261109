"""KS-Fix 코어 API: bytes → 결과(네트워크·subprocess·전역 상태 없음)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from ksfix import __version__
from ksfix.model import KSDoc, Para, Role, Table
from ksfix.model.builder import build
from ksfix.rules.base import SEVERITY_ORDER, Finding
from ksfix.rules.registry import load_catalog, make_context, run_rules, select_rules


def analyze(data: bytes) -> KSDoc:
    """docx bytes → 구조 인식까지 마친 KSDoc."""
    doc = build(data)
    try:
        from ksfix.classify import classify
    except ImportError:  # 구조 인식 모듈이 없을 때(개발 초기)
        return doc
    classify(doc)
    return doc


def _para_row(p: Para) -> dict[str, Any]:
    return {
        "idx": p.idx,
        "section": p.section_idx,
        "role": p.role.value,
        "conf": round(p.role_conf, 2),
        "style": p.style_name,
        "label": p.num_label,
        "level": p.attrs.get("level"),
        "clause": p.clause_no,
        "in_table": p.in_table,
        "text": p.text,
    }


def inspect_bytes(data: bytes) -> dict[str, Any]:
    doc = analyze(data)
    return {
        "meta": doc.meta,
        "blocks": [_para_row(p) for p in doc.paras],
        "tables": [
            {
                "idx": t.idx,
                "rows": len(t.cells),
                "cols": max((len(r) for r in t.cells), default=0),
                "nested": t.nested,
                "first_para": t.paras[0].idx if t.paras else None,
            }
            for t in doc.tables
            if isinstance(t, Table)
        ],
    }


@dataclass
class CheckResult:
    doc: KSDoc
    findings: list[Finding]
    rules: set[str]
    diagnostics: list[dict] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        c = {"error": 0, "warning": 0, "info": 0}
        for f in self.findings:
            c[f.severity] += 1
        return c

    def summary(self) -> dict[str, Any]:
        cat = load_catalog()
        failed = {f.rule_id for f in self.findings}
        applied = sorted(self.rules)
        passed = [r for r in applied if r not in failed]
        return {
            "findings": len(self.findings),
            "by_severity": self.counts(),
            "autofixable": sum(1 for f in self.findings if f.autofixable),
            "needs_review": sum(1 for f in self.findings if not f.autofixable),
            "rules_applied": len(applied),
            "rules_passed": len(passed),
            "pass_rate": round(100 * len(passed) / len(applied), 1) if applied else 100.0,
            "rule_pack": f"{cat.pack} {cat.version}",
        }


def doc_warnings(doc: KSDoc) -> list[str]:
    out = []
    if not doc.meta.get("ks_target", True):
        out.append("한글 비율이 낮아 KS A 0001 적용 대상이 아닐 수 있습니다(영문 원문 등).")
    if doc.meta.get("has_tracked_changes"):
        out.append(
            "기존 변경추적이 있습니다. 수락된 상태로 읽었으며, 자동 수정 대신 메모만 남깁니다."
        )
    n_low = doc.meta.get("low_confidence", 0)
    if n_low:
        out.append(f"구조 인식 신뢰도가 낮은 블록 {n_low}개는 일부 규칙에서 제외했습니다.")
    return out


def check_bytes(data: bytes, *, rules: str | None = None, llm: Any = None) -> CheckResult:
    """docx bytes → 지적 목록(문서는 바꾸지 않는다)."""
    t0 = time.perf_counter()
    doc = analyze(data)
    t1 = time.perf_counter()
    active = select_rules(rules)
    ctx = make_context(active, llm=llm)
    findings = run_rules(doc, ctx)
    t2 = time.perf_counter()
    findings.sort(key=lambda f: (f.block, f.start or 0, SEVERITY_ORDER[f.severity], f.rule_id))
    return CheckResult(
        doc=doc,
        findings=findings,
        rules=active,
        diagnostics=ctx.diagnostics,
        timings={"analyze": round(t1 - t0, 3), "rules": round(t2 - t1, 3)},
        warnings=doc_warnings(doc),
    )


def findings_json(result: CheckResult) -> list[dict[str, Any]]:
    out = []
    paras = result.doc.paras
    for f in result.findings:
        d = f.to_dict()
        p = paras[f.block] if 0 <= f.block < len(paras) else None
        d["role"] = p.role.value if p is not None else None
        d["clause_no"] = p.clause_no if p is not None else None
        d["location"] = _location(p)
        out.append(d)
    return out


def _location(p: Para | None) -> str:
    if p is None:
        return ""
    if p.role == Role.HEADING and p.attrs.get("number"):
        return f"{p.attrs['number']} 제목"
    where = p.clause_no or {
        "foreword": "머리말",
        "intro": "개요",
        "toc": "목차",
        "title": "제목",
        "biblio": "참고문헌",
        "commentary": "해설",
        "cover": "표지",
        "back_cover": "뒤표지",
    }.get(p.attrs.get("zone", ""), "")
    if p.in_table:
        return f"{where} 표 {p.table_idx + 1 if p.table_idx is not None else ''}".strip()
    return where


def report_dict(
    result: CheckResult, *, source_name: str, extra: dict | None = None
) -> dict[str, Any]:
    doc = result.doc
    meta = {k: v for k, v in doc.meta.items() if k not in ("rule_timings",)}
    return {
        "tool": {"name": "KS-Fix", "version": __version__},
        "source": {"name": source_name, "sha256": doc.meta.get("sha256")},
        "summary": result.summary(),
        "warnings": result.warnings,
        "document": meta,
        "findings": findings_json(result),
        "diagnostics": result.diagnostics,
        "timings": result.timings,
        **(extra or {}),
    }
