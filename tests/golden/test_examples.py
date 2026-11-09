"""examples/가 현재 엔진 결과와 같은지 확인(규칙을 바꾸고 예시를 다시 만들지 않으면 실패)."""

import io
import json

import docx
import pytest

from ksfix import __version__
from ksfix.api import check_bytes, fix_bytes
from tests.conftest import ROOT

EXAMPLES = ROOT / "examples"
DATE = "2026-11-11T00:00:00Z"
HINT = (
    "규칙·수정 엔진이 바뀌었습니다. `python scripts/make_examples.py`로 examples/를 다시 만드세요."
)


def _load(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def _keys(findings) -> list[tuple]:
    return sorted((f["rule_id"], f["block"], f["start"], f.get("status")) for f in findings)


@pytest.mark.skipif(not EXAMPLES.is_dir(), reason="examples/ 없음")
def test_examples_match_engine(sample_bytes):
    from ksfix.report import build_report

    rep = _load("sample_01_violations.ksfix-report.json")
    assert rep["tool"]["version"] == __version__, HINT
    res = fix_bytes(sample_bytes["sample_01_violations"], mode="tracked", date=DATE)
    fresh = build_report(
        res.check, res, source_name="sample_01_violations.docx", input_unchanged=True
    )
    assert rep["summary"] == fresh["summary"], HINT
    assert _keys(rep["findings"]) == _keys(fresh["findings"]), HINT
    clean = _load("sample_02_clean.ksfix-report.json")
    assert clean["summary"]["findings"] == len(
        check_bytes(sample_bytes["sample_02_clean"]).findings
    ), HINT


@pytest.mark.skipif(not EXAMPLES.is_dir(), reason="examples/ 없음")
def test_example_outputs_open():
    for name in (
        "sample_01_violations.ksfix-tracked.docx",
        "sample_01_violations.ksfix-clean.docx",
    ):
        d = docx.Document(io.BytesIO((EXAMPLES / name).read_bytes()))
        assert d.paragraphs
    html = (EXAMPLES / "sample_01_violations.ksfix-report.html").read_text(encoding="utf-8")
    assert "KS-Fix" in html and "<script src=" not in html  # 단일 파일(외부 스크립트 없음)
