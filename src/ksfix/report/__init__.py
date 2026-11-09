"""리포트: JSON(기계 판독)·HTML(사람용)·부속서 A 체크리스트·감사 로그."""

from ksfix.report.html_report import render_html
from ksfix.report.json_report import build_report

__all__ = ["build_report", "render_html"]
