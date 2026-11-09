"""단일 파일 HTML 리포트(CSS·JS 인라인, 외부 리소스 없음)."""

from __future__ import annotations

import json
from functools import cache
from typing import Any

from jinja2 import Environment, PackageLoader, select_autoescape

MODE_KO = {
    "check": "점검",
    "tracked": "변경추적 교정",
    "clean": "반영본 교정",
    "report": "리포트만",
}
SEV_KO = {"error": "오류", "warning": "경고", "info": "참고"}
PILL = {
    "자동수정": "fixed",
    "자동수정 가능": "fixed",
    "제안": "sugg",
    "AI 제안": "sugg",
    "판단 필요": "sugg",
    "검토 필요": "review",
}
CL_PILL = {
    "pass": "pass",
    "fail": "fail",
    "partial_pass": "part",
    "partial_fail": "fail",
    "manual": "man",
    "not_run": "man",
}


@cache
def _env() -> Environment:
    return Environment(
        loader=PackageLoader("ksfix.report", "templates"),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_html(report: dict[str, Any]) -> str:
    data_json = json.dumps(report, ensure_ascii=False).replace("</", "<\\/")
    statuses = sorted({f["status_label"] for f in report["findings"]})
    return (
        _env()
        .get_template("report.html.j2")
        .render(
            r=report,
            data_json=data_json,
            mode_ko=MODE_KO.get(report["mode"], report["mode"]),
            sev_ko=SEV_KO,
            pill=PILL,
            cl_pill=CL_PILL,
            statuses=statuses,
        )
    )
