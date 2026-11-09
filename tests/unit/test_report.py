"""리포트: 오프라인 단일 HTML, 체크리스트 53항목, HTML 수치 = JSON 수치."""

import json
import re

import pytest

from ksfix.api import check_bytes, fix_bytes
from ksfix.report import build_report, render_html
from ksfix.report.checklist import load_checklist


@pytest.fixture(scope="module")
def fixed_report(sample_bytes):
    r = fix_bytes(sample_bytes["sample_01_violations"], mode="tracked")
    rep = build_report(r.check, r, source_name="sample_01.docx", input_unchanged=True)
    return rep, render_html(rep)


def test_checklist_has_all_annex_a_items(fixed_report):
    rep, _ = fixed_report
    items = rep["checklist"]["items"]
    assert len(items) == len(load_checklist()) == 53
    assert [i["id"] for i in items] == [f"A{n:02d}" for n in range(1, 54)]
    assert all(i["status"] and i["label"] for i in items)
    groups = {i["group"] for i in items}
    assert len(groups) == 18


def test_html_is_offline_single_file(fixed_report):
    _, html = fixed_report
    assert not re.search(r"<(script|img|iframe)[^>]+src=", html)
    assert not re.search(r"<link[^>]+href=", html)
    assert "@import" not in html and "url(http" not in html


def test_html_numbers_equal_json(fixed_report):
    rep, html = fixed_report
    m = re.search(r'<script type="application/json" id="ksfix-data">(.*?)</script>', html, re.S)
    embedded = json.loads(m.group(1).replace("<\\/", "</"))
    assert embedded["summary"] == rep["summary"]
    cards = dict(re.findall(r'data-key="(\w+)" data-value="([\d.]+)"', html))
    s = rep["summary"]
    assert int(cards["findings"]) == s["findings"]
    assert int(cards["applied"]) == s["applied"]
    assert int(cards["needs_review"]) == s["needs_review"]
    assert float(cards["pass_rate"]) == s["pass_rate_before"]
    assert int(cards["checklist"]) == rep["checklist"]["summary"]["total"]
    assert html.count('<tr data-sev="') == s["findings"]


def test_report_statuses_and_verification(fixed_report):
    rep, _ = fixed_report
    labels = {f["status_label"] for f in rep["findings"]}
    assert "자동수정" in labels
    assert rep["verification"]["invariants"]["ok"] is True
    assert rep["verification"]["integrity"] == []
    assert rep["summary"]["pass_rate_after"] > rep["summary"]["pass_rate_before"]
    assert sum(c["count"] for c in rep["categories"]) == rep["summary"]["findings"]


def test_check_only_report(sample_bytes):
    res = check_bytes(sample_bytes["sample_02_clean"])
    rep = build_report(res, None, source_name="clean.docx")
    html = render_html(rep)
    assert rep["mode"] == "check" and rep["summary"]["applied"] == 0
    assert "자동수정 가능" in html


def test_html_escapes_document_text(sample_bytes):
    res = check_bytes(sample_bytes["sample_01_violations"])
    rep = build_report(res, None, source_name="<script>x</script>.docx")
    html = render_html(rep)
    assert "<script>x</script>" not in html
    assert "&lt;표 1&gt;" in html
