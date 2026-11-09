"""Phase 8 규칙: 양성·음성 예와 실제 문서에서 찾은 오탐 사례(내용은 합성으로 재현)."""

from ksfix.api import check_bytes, fix_bytes
from tests.helpers import ks_skeleton, make_docx

NORMREF = [
    {"text": "2 인용표준", "bold": True},
    "다음의 인용표준은 전체 또는 부분적으로 이 표준의 적용을 위해 필수적이다. 발행연도가 표기된 "
    "인용표준은 인용된 판만을 적용한다. 발행연도가 표기되지 않은 인용표준은 최신판(모든 추록을 포함)을 적용한다.",
    "KS A 0006, 시험 장소의 표준 상태",
    {"text": "3 용어와 정의", "bold": True},
    "이 표준의 목적을 위하여 다음의 용어와 정의를 적용한다.",
    {"text": "3.1", "bold": True},
    {"text": "최대 칭량(maximum capacity)", "bold": True},
    "표시할 수 있는 최대 질량값",
]


def check(body, rules, extra_front=None):
    items = ks_skeleton(NORMREF + body)
    if extra_front:
        items = extra_front + items
    return check_bytes(make_docx(items), rules=rules).findings


def ids(fs):
    return sorted(f.rule_id for f in fs)


def test_num01_num02_num03():
    body = [
        {"text": "4 요구사항", "bold": True},
        {"text": "4.1 구조", "bold": True},
        "구조는 단단하여야 한다.",
        {"text": "6 표시", "bold": True},
    ]
    fs = check(body, "NUM-01,NUM-02")
    assert ids(fs) == ["NUM-01", "NUM-02"]


def test_str03_hanging_and_exempt_clauses():
    body = [
        {"text": "4 요구사항", "bold": True},
        "이 절은 요구사항을 규정한다.",
        {"text": "4.1 구조", "bold": True},
        "구조는 단단하여야 한다.",
        {"text": "4.2 표시", "bold": True},
        "표시는 지워지지 않아야 한다.",
    ]
    fs = check(body, "STR-03")
    assert len(fs) == 1 and "미결문단" in fs[0].message


def test_str04_requirement_in_note_but_not_in_quotes():
    body = [
        {"text": "4 요구사항", "bold": True},
        "비고 시험 장소에는 진동원이 없어야 한다.",
        "비고 “……하여야 한다.”는 요구사항을 나타낸다.",
    ]
    fs = check(body, "STR-04")
    assert len(fs) == 1 and "진동원" in fs[0].snippet


def test_pun01_pun06():
    body = [
        {"text": "4 요구사항", "bold": True},
        "전원은 건전지를 쓴다; 어댑터는 별매품이다.",
        "표시값을 읽는다..",
        "비고  25 ℃의 기준 온도는 부속서 C를 따른다.",
        "체중계의  표시부는 밝아야 한다.",
    ]
    fs = check(body, "PUN-01,PUN-06")
    assert ids(fs) == ["PUN-01", "PUN-06", "PUN-06"]  # 라벨 뒤 정렬 공백은 지적하지 않음


def test_qty02_qty03_qty05_qty06():
    body = [
        {"text": "4 요구사항", "bold": True},
        "눈금 간격은 .1 kg 이하로 한다.",
        "받침판은 2,000 N의 하중을 견뎌야 한다.",
        "시험 온도는 5 ∼ 40 ℃로 한다.",
        "패드는 40 mm x 40 mm 이상이어야 한다.",
        "범위는 (10 ∼ 40) ℃ 또는 10 ℃ ∼ 40 ℃로 쓴다.",
        "2021년 1000개를 만들었다.",
    ]
    fs = check(body, "QTY-02,QTY-03,QTY-05,QTY-06")
    assert ids(fs) == ["QTY-02", "QTY-03", "QTY-05", "QTY-06"]
    q5 = next(f for f in fs if f.rule_id == "QTY-05")
    assert q5.suggestion == "5 ℃ ∼ 40 ℃"


def test_nte01_terms_counted_per_entry_and_unit_numbers():
    body = [
        {"text": "3.2", "bold": True},
        {"text": "눈금 간격(scale interval)", "bold": True},
        "인접한 표시값의 차이",
        "비고 눈금 간격은 kg으로 표시한다.",
        {"text": "3.3", "bold": True},
        {"text": "영점(zero)", "bold": True},
        "하중이 없을 때의 표시값",
        "비고 영점은 자동으로 맞춘다.",
        {"text": "4 요구사항", "bold": True},
        "비고 1 표시부는 밝다.",
    ]
    fs = check(body, "NTE-01")
    assert len(fs) == 1 and fs[0].suggestion == "비고"


def test_nrf_rules_and_false_positive_cases():
    normref = [
        {"text": "2 인용표준", "bold": True},
        NORMREF[1],
        "IEC 61010-1:2010, Safety requirements",
        "KS A 0006, 시험 장소의 표준 상태 — 측정 방법",
        "계량에 관한 법률",
        "ISO 3:1973에 대응되는 KS는 2012년도에 고시된 KS A ISO 3이다.",
    ]
    items = ks_skeleton(
        normref
        + NORMREF[3:]
        + [{"text": "4 요구사항", "bold": True}, "정전기 시험은 KS C IEC 61000-4-2에 따른다."]
    )
    fs = check_bytes(make_docx(items), rules="NRF-01,NRF-02,NRF-03").findings
    assert ids(fs) == ["NRF-01", "NRF-02", "NRF-03"]
    nrf3 = next(f for f in fs if f.rule_id == "NRF-03")
    assert "법률" in nrf3.snippet


def test_trm01_trm02_and_fix_in_heading_with_break():
    body = [
        {"text": "3.2", "bold": True},
        {"text": "눈금 간격 (Scale interval)", "bold": True},
        "인접한 두 표시값 사이의 차이.",
    ]
    fs = check(body, "TRM-01,TRM-02")
    assert ids(fs) == ["TRM-01", "TRM-01", "TRM-02"]


def test_tbl02_fig02_moves_and_invariants():
    body = [
        {"text": "4 요구사항", "bold": True},
        "표 1에 따른다.",
        {"table": [["항목", "값"], ["길이", "10"]]},
        {"text": "<표 1> 측정 범위", "center": True},
    ]
    data = make_docx(ks_skeleton(NORMREF + body))
    r = fix_bytes(data, mode="tracked", rules="TBL-01,TBL-02")
    assert r.invariants["ok"] and not r.integrity
    assert {d.finding.rule_id for d in r.decisions if d.action == "apply"} == {"TBL-01", "TBL-02"}
    after = check_bytes(r.output, rules="TBL-01,TBL-02")
    assert after.findings == []


def test_toc02_and_ttl_rules():
    front = [
        {"text": "목    차", "bold": True, "center": True},
        "1\t적용범위\t1",
        "2\t인용 규격\t1",
    ]
    fs = check([], "TOC-01,TOC-02", extra_front=front)
    assert ids(fs) == ["TOC-01", "TOC-02"]
