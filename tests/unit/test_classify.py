import json

import pytest
from tests.helpers import ks_skeleton, make_docx

from ksfix.api import analyze
from ksfix.classify.heuristics import plausible_next
from ksfix.model import Role


@pytest.mark.parametrize(
    "name", ["sample_01_violations", "sample_02_clean", "sample_03_messy_styles"]
)
def test_role_accuracy_at_least_95(samples_dir, sample_bytes, name):
    doc = analyze(sample_bytes[name])
    prefix = "_".join(name.split("_")[:2])
    gold = json.loads((samples_dir / f"{prefix}_roles.json").read_text(encoding="utf-8"))
    pred = [p.role.value for p in doc.paras]
    acc = sum(a == b for a, b in zip(gold, pred, strict=True)) / len(gold)
    assert acc >= 0.95, acc


def test_clean_sample_structure(sample_bytes):
    doc = analyze(sample_bytes["sample_02_clean"])
    assert doc.meta["std_number"] == "KS X 9999:2026"
    assert doc.meta["title_ko"].startswith("디지털 체중계")
    assert doc.meta["title_en"].startswith("Digital body weight scales")
    annexes = [n for n in doc.tree.children if n.kind == "annex"]
    assert [(a.number, a.status, a.title) for a in annexes] == [
        ("A", "규정", "교정 절차"),
        ("B", "참고", "사용상의 주의"),
    ]
    tops = [n.number for n in doc.tree.children if n.kind == "clause"]
    assert tops == ["1", "2", "3", "4", "5", "6", "7"]
    para = next(p for p in doc.paras if p.text.startswith("표시부의 글자 높이"))
    assert para.clause_no == "4.2"
    terms = doc.by_role(Role.TERM)
    assert [t.attrs.get("number") for t in terms] == ["3.1", "3.2", "3.3"]
    assert len(doc.by_role(Role.DEFINITION)) == 3
    parts = doc.meta["parts"]
    for key in ("cover", "front", "body", "annex", "biblio", "commentary", "back_cover"):
        assert key in parts
    assert parts["body"][1] < parts["annex"][0] < parts["biblio"][0] < parts["commentary"][0]


def test_messy_sample_typed_structure(sample_bytes):
    doc = analyze(sample_bytes["sample_03_messy_styles"])
    tops = [n.number for n in doc.tree.children if n.kind == "clause"]
    assert tops == ["1", "2", "3", "4", "5", "6", "7"]
    assert [p.attrs.get("number") for p in doc.by_role(Role.TERM)] == ["3.1", "3.2", "3.3"]
    assert len(doc.by_role(Role.ANNEX_STATUS)) == 2


def test_plausible_next():
    assert plausible_next(None, "1")
    assert plausible_next("4", "4.1")
    assert plausible_next("4.2", "5")
    assert plausible_next("4.2", "4.3")
    assert plausible_next("4.2.1", "4.3")
    assert not plausible_next("9.1", "1")
    assert not plausible_next("9.1", "2")
    assert plausible_next(None, "A.1")
    assert plausible_next("A.1", "A.2")
    assert not plausible_next("A.2", "B.3")


def test_trap_toc_entries_and_body_sentences_are_not_captions():
    # §4.3 함정 2·3: 목차 항목("표 12 — … 23")과 "표 2를 참조한다."는 캡션이 아니다
    data = make_docx(
        [
            {"text": "목    차", "bold": True, "center": True},
            "표 12 — 측정 결과\t23",
            *ks_skeleton(
                [
                    "표 2를 참조한다.",
                    "그림 3에 따라 설치한다.",
                    {"text": "표 1 — 측정 범위", "bold": True, "center": True},
                    {"table": [["항목", "값"], ["길이", "10"]]},
                ]
            ),
        ]
    )
    doc = analyze(data)
    by_text = {p.text: p for p in doc.paras}
    assert by_text["표 12 — 측정 결과\t23"].role == Role.TOC_ENTRY
    assert by_text["표 2를 참조한다."].role == Role.BODY
    assert by_text["그림 3에 따라 설치한다."].role == Role.BODY
    assert by_text["표 1 — 측정 범위"].role == Role.TABLE_CAPTION


def test_trap_spaced_titles_recognized():
    # §4.3 함정 11: 글자 사이를 띄운 제목
    data = make_docx(
        [
            {"text": "목    차", "center": True, "bold": True},
            {"text": "머  리  말", "center": True, "bold": True},
            "이 표준은 시험이다.",
            {"text": "개    요", "center": True, "bold": True},
            "개요 문장이다.",
        ]
    )
    roles = [p.role for p in analyze(data).paras]
    assert Role.TOC_TITLE in roles and Role.FOREWORD_TITLE in roles and Role.INTRO_TITLE in roles


def test_trap_both_term_entry_forms(sample_bytes):
    # §4.3 함정 12: 자동번호 Heading + 줄바꿈 + 용어 / 본문에 "3.1"을 따로 입력
    ksdt = analyze(sample_bytes["sample_02_clean"])
    typed = analyze(sample_bytes["sample_03_messy_styles"])
    assert {t.attrs["term"] for t in ksdt.by_role(Role.TERM)} == {
        t.attrs["term"] for t in typed.by_role(Role.TERM)
    }


def test_figure_legend_numbers_are_not_headings():
    data = make_docx(
        ks_skeleton(
            [
                {"text": "2 시험 방법", "bold": True},
                "시험은 다음과 같이 한다.",
                "1\t용접봉 홀더",
                "2\t둥근 봉",
                {"text": "3 표시", "bold": True},
            ]
        )
    )
    doc = analyze(data)
    tops = [n.number for n in doc.tree.children if n.kind == "clause"]
    assert tops == ["1", "2", "3"]
