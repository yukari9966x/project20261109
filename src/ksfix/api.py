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


@dataclass
class FixResult:
    check: CheckResult
    mode: str
    output: bytes | None
    decisions: list
    audit: list[dict]
    after: CheckResult | None
    invariants: dict
    integrity: list[str]
    comments: int
    timings: dict[str, float]
    remaining_autofix: int = 0

    def summary(self) -> dict[str, Any]:
        before = self.check.summary()
        applied = sum(1 for d in self.decisions if d.action == "apply")
        out = {
            "mode": self.mode,
            "applied": applied,
            "suggested": sum(1 for d in self.decisions if d.action == "suggest"),
            "reported": sum(1 for d in self.decisions if d.action == "report"),
            "comments": self.comments,
            "pass_rate_before": before["pass_rate"],
            "pass_rate_after": self.after.summary()["pass_rate"] if self.after else None,
            "findings_after": len(self.after.findings) if self.after else None,
            "remaining_autofix": self.remaining_autofix,
            "invariants_ok": self.invariants.get("ok", True),
            "integrity_ok": not self.integrity,
        }
        return out


def _reset(findings: list[Finding]) -> None:
    for f in findings:
        f.status = "open"


def _render(data: bytes, findings: list[Finding], mode: str, allow_edits: bool, date: str | None):
    from ksfix.fix import apply_decisions, plan

    doc = analyze(data)
    decisions = plan(doc, findings, mode, allow_edits=allow_edits)
    res = apply_decisions(doc, decisions, mode, date=date)
    return res, decisions


def fix_bytes(
    data: bytes,
    *,
    mode: str = "tracked",
    rules: str | None = None,
    llm: Any = None,
    accept_existing_changes: bool = False,
    date: str | None = None,
) -> FixResult:
    """docx bytes → 교정 문서 bytes(tracked|clean) 또는 리포트만(report)."""
    from ksfix.fix import plan
    from ksfix.fix.invariants import diff, doc_tokens, integrity_problems, is_clean

    if mode not in ("tracked", "clean", "report"):
        raise ValueError(f"알 수 없는 모드: {mode}")
    t0 = time.perf_counter()
    chk = check_bytes(data, rules=rules, llm=llm)
    allow = accept_existing_changes or not chk.doc.meta.get("has_tracked_changes")
    res, decisions = _render(data, chk.findings, mode, allow, date)
    t1 = time.perf_counter()
    invariants: dict[str, Any] = {"ok": True}
    integrity: list[str] = []
    after = None
    remaining = 0
    if res.data is not None:
        integrity = integrity_problems(res.data)
        after = check_bytes(res.data, rules=rules)
        d = diff(doc_tokens(chk.doc), doc_tokens(after.doc), res.allowed_extra)
        if not is_clean(d):
            # INV-01 안전망: 편집을 모두 철회하고 메모만 남긴 문서로 다시 만든다
            _reset(chk.findings)
            res, decisions = _render(data, chk.findings, mode, False, date)
            for dec in decisions:
                if dec.finding.fix is not None and dec.finding.fix.auto:
                    dec.reason = "INV-01: 결과 문서 검증에서 기술적 내용 변화가 발견되어 철회"
            integrity = integrity_problems(res.data) if res.data else []
            after = check_bytes(res.data, rules=rules) if res.data else None
            invariants = {"ok": False, "reverted": True, **d}
        if after is not None:
            remaining = sum(
                1 for x in plan(after.doc, after.findings, "clean") if x.action == "apply"
            )
    t2 = time.perf_counter()
    return FixResult(
        check=chk,
        mode=mode,
        output=res.data,
        decisions=decisions,
        audit=res.audit,
        after=after,
        invariants=invariants,
        integrity=integrity,
        comments=res.comments,
        timings={**chk.timings, "fix": round(t1 - t0, 3), "verify": round(t2 - t1, 3)},
        remaining_autofix=remaining,
    )
