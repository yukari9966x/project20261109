"""부속서 A 검토 항목 체크리스트: 규칙 결과로 항목별 상태를 정한다."""

from __future__ import annotations

from collections import Counter
from functools import cache
from importlib import resources

import yaml

from ksfix.rules.base import Finding

STATUS_LABEL = {
    "pass": "자동 통과",
    "fail": "자동 지적",
    "partial_pass": "부분 자동(지적 없음)",
    "partial_fail": "부분 자동(지적 있음)",
    "manual": "수동 확인",
    "not_run": "수동 확인(규칙 미구현)",
}


@cache
def load_checklist(pack: str = "ksa0001_2023") -> list[dict]:
    text = (
        resources.files("ksfix.rules.packs")
        .joinpath(pack, "checklist.yaml")
        .read_text(encoding="utf-8")
    )
    return yaml.safe_load(text)["items"]


def build_checklist(findings: list[Finding], active: set[str]) -> list[dict]:
    counts = Counter(f.rule_id for f in findings)
    out = []
    for item in load_checklist():
        rules = list(item.get("rules") or [])
        ran = [r for r in rules if r in active]
        n = sum(counts[r] for r in ran)
        if item["type"] == "manual" or not rules:
            status = "manual"
        elif not ran:
            status = "not_run"
        elif item["type"] == "auto" and len(ran) == len(rules):
            status = "fail" if n else "pass"
        else:
            status = "partial_fail" if n else "partial_pass"
        label = STATUS_LABEL[status] + (f" {n}건" if n else "")
        out.append(
            {
                "id": item["id"],
                "group": item["group"],
                "ref": item["ref"],
                "summary": item["summary"],
                "rules": rules,
                "rules_run": ran,
                "type": item["type"],
                "manual": item.get("manual"),
                "status": status,
                "label": label,
                "findings": n,
            }
        )
    return out


def checklist_summary(items: list[dict]) -> dict[str, int]:
    c = Counter(i["status"] for i in items)
    return {
        "total": len(items),
        "auto_pass": c["pass"],
        "auto_fail": c["fail"],
        "partial": c["partial_pass"] + c["partial_fail"],
        "manual": c["manual"] + c["not_run"],
    }
