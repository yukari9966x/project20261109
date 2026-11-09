"""KS-Fix 코어 API: bytes → 결과(네트워크·subprocess·전역 상태 없음)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from ksfix.model import KSDoc, Para, Table
from ksfix.model.builder import build
from ksfix.rules.base import SEVERITY_ORDER, Finding
from ksfix.rules.registry import load_catalog, make_context, run_rules, select_rules


def analyze(data: bytes, llm: Any = None) -> KSDoc:
    """docx bytes → 구조 인식까지 마친 KSDoc(LLM이 있으면 저신뢰 블록을 T2로 보조)."""
    from ksfix.classify import classify

    doc = build(data)
    classify(doc)
    if llm is not None and doc.meta.get("low_confidence"):
        from ksfix.llm.tasks.classify_blocks import assist

        doc.meta["llm_reclassified"] = assist(doc, llm)
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
    llm_profile: str | None = None
    llm_model: str | None = None
    llm_external: bool = False

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
    doc = analyze(data, llm)
    t1 = time.perf_counter()
    active = select_rules(rules)
    ctx = make_context(active, llm=llm)
    findings = run_rules(doc, ctx)
    t2 = time.perf_counter()
    findings.sort(key=lambda f: (f.block, f.start or 0, SEVERITY_ORDER[f.severity], f.rule_id))
    warnings = doc_warnings(doc)
    if llm is not None and getattr(llm, "external", False):
        warnings.insert(
            0, f"외부 LLM({llm.name})을 사용했습니다. 후보 문장이 외부로 전송되었습니다."
        )
    return CheckResult(
        doc=doc,
        findings=findings,
        rules=active,
        diagnostics=ctx.diagnostics,
        timings={"analyze": round(t1 - t0, 3), "rules": round(t2 - t1, 3)},
        warnings=warnings,
        llm_profile=(getattr(llm, "name", "") or "").split("/")[0] or None,
        llm_model=getattr(llm, "model", None),
        llm_external=bool(getattr(llm, "external", False)),
    )


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
        after = check_bytes(res.data, rules=rules, llm=llm)
        d = diff(doc_tokens(chk.doc), doc_tokens(after.doc), res.allowed_extra)
        if not is_clean(d):
            # INV-01 안전망: 편집을 모두 철회하고 메모만 남긴 문서로 다시 만든다
            _reset(chk.findings)
            res, decisions = _render(data, chk.findings, mode, False, date)
            for dec in decisions:
                if dec.finding.fix is not None and dec.finding.fix.auto:
                    dec.reason = "INV-01: 결과 문서 검증에서 기술적 내용 변화가 발견되어 철회"
            integrity = integrity_problems(res.data) if res.data else []
            after = check_bytes(res.data, rules=rules, llm=llm) if res.data else None
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
