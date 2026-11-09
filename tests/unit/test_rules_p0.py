"""첫 규칙 묶음의 양성·음성 테스트와 §4.3 함정 1·2·4·6·7·8."""

from ksfix.api import check_bytes
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
    {"text": "4 요구사항", "bold": True},
]


def run(body, rules):
    return check_bytes(make_docx(ks_skeleton(NORMREF + body)), rules=rules).findings


def ids(findings):
    return [f.rule_id for f in findings]


# ── PUN-02 ──
def test_pun02_positive_and_fix():
    fs = run(["시험 온도는 10 ~ 40 ℃로 한다."], "PUN-02")
    assert ids(fs) == ["PUN-02"]
    assert fs[0].fix.text == "∼" and fs[0].fix.auto


def test_pun02_negative_url_and_correct_mark():
    assert (
        run(
            ["자료: http://example.com/~user/data 를 참고한다.", "시험 온도는 10 ∼ 40으로 한다."],
            "PUN-02",
        )
        == []
    )


def test_trap7_table_cell_range_only_mark_changes():
    fs = run([{"table": [["범위", "값"], ["1.6 ~ 2.5", "10"]]}], "PUN-02,QTY-01")
    assert ids(fs) == ["PUN-02"]
    assert fs[0].fix.start == fs[0].fix.end - 1 and fs[0].fix.text == "∼"


# ── QTY-01 ──
def test_qty01_multichar_unit_autofix():
    fs = run(["최대 칭량은 150kg 이상이어야 한다."], "QTY-01")
    assert ids(fs) == ["QTY-01"] and fs[0].fix.auto and fs[0].severity == "warning"
    assert fs[0].suggestion == "150 kg"


def test_trap4_single_letter_units_suggest_only():
    fs = run(
        [
            "전원은 12V를 쓴다.",
            "그룹 1A 커패시터",
            "M8 볼트를 A4 용지와 IP65 함에 넣는다.",
            "3D 형상",
        ],
        "QTY-01",
    )
    assert len(fs) == 1
    assert fs[0].severity == "info" and not fs[0].fix.auto


def test_trap6_nbsp_is_valid_space():
    assert run(["시험 온도는 10 ℃이고 습도는 60 %이다.", "길이는 5 mm이다."], "QTY-01") == []


# ── QTY-04 ──
def test_qty04_tolerance_parentheses():
    fs = run(["시험은 23 ± 2 ℃에서 한다."], "QTY-04")
    assert ids(fs) == ["QTY-04"] and fs[0].suggestion == "(23 ± 2) ℃"


def test_qty04_negative_forms():
    assert (
        run(["시험은 (23 ± 2) ℃에서 한다.", "시험은 23 ℃ ± 2 ℃에서 한다.", "± 0.1"], "QTY-04") == []
    )


# ── TBL-01·FIG-01 ──
def test_tbl01_and_fig01_caption_forms():
    body = [
        {"text": "<표 1> 측정 범위", "center": True},
        {"table": [["항목", "값"], ["a", "1"]]},
        {"text": "표 2 — 올바른 제목", "center": True},
        {"table": [["항목", "값"], ["b", "2"]]},
        {"text": "그림1. 구조", "center": True},
        {"text": "표 13 —최대 변화량", "center": True},
    ]
    fs = run(body, "TBL-01,FIG-01")
    got = {(f.rule_id, f.suggestion) for f in fs}
    assert got == {
        ("TBL-01", "표 1 — 측정 범위"),
        ("FIG-01", "그림 1 — 구조"),
        ("TBL-01", "표 13 — 최대 변화량"),
    }


def test_trap2_toc_entries_not_checked_as_captions():
    data = make_docx(
        [
            {"text": "목    차", "bold": True, "center": True},
            "표 12 —측정 결과\t23",
            *ks_skeleton(NORMREF),
        ]
    )
    assert check_bytes(data, rules="TBL-01").findings == []


# ── REF-01 ──
def test_ref01_missing_targets():
    fs = run(
        [
            "자세한 조건은 표 5 참조.",
            "시험은 5.2에 따른다.",
            "그림 3과 같이 설치한다.",
            "부속서 C를 따른다.",
        ],
        "REF-01",
    )
    assert sorted(f.extra["ref"] for f in fs) == ["3", "5", "5.2", "C"]
    assert all(f.severity == "error" for f in fs)


def test_trap1_other_standard_elements_excluded():
    body = [
        "IEC 60974-1:2017의 표 6에 따른다.",
        "KS C IEC 60384-1:2016의 2.4와 2.5를 참조한다.",
        "개별 규격의 1.9에 열거한다.",
        "하중은 정격의 1.5배로 한다.",
        "이 표준은 2021년 제4.0판을 기초로 한다.",
        "3.1에 정의된 최대 칭량을 쓴다.",
    ]
    assert run(body, "REF-01") == []


# ── BLT-03·BLT-04 ──
def _skeleton_with(normref_intro, terms_intro):
    items = [
        {"text": "2 인용표준", "bold": True},
        *([normref_intro] if normref_intro else []),
        "KS A 0006, 시험 장소의 표준 상태",
        {"text": "3 용어와 정의", "bold": True},
        *([terms_intro] if terms_intro else []),
        {"text": "3.1", "bold": True},
        {"text": "최대 칭량(maximum capacity)", "bold": True},
        "표시할 수 있는 최대 질량값",
    ]
    return make_docx(ks_skeleton(items))


def test_blt03_altered_boilerplate_autofix():
    altered = NORMREF[1].replace("필수적이다", "필요하다")
    fs = check_bytes(_skeleton_with(altered, NORMREF[4]), rules="BLT-03").findings
    assert ids(fs) == ["BLT-03"] and fs[0].fix.auto and fs[0].fix.kind == "replace_text"


def test_blt03_missing_boilerplate_inserted():
    fs = check_bytes(_skeleton_with(None, NORMREF[4]), rules="BLT-03").findings
    assert ids(fs) == ["BLT-03"] and fs[0].fix.kind == "insert_paragraph_after"


def test_blt04_second_form_accepted_and_variant_suggested():
    ok = "이 표준의 목적을 위하여 KS C IEC 60050-151에 규정된 용어와 정의 및 다음을 적용한다."
    assert check_bytes(_skeleton_with(NORMREF[1], ok), rules="BLT-04").findings == []
    variant = "이 표준의 목적을 위하여 KS C IEC 60384-1 및 다음의 용어와 정의를 적용한다."
    fs = check_bytes(_skeleton_with(NORMREF[1], variant), rules="BLT-04").findings
    assert ids(fs) == ["BLT-04"]
    assert (
        fs[0].suggestion
        == "이 표준의 목적을 위하여 KS C IEC 60384-1에 규정된 용어와 정의 및 다음을 적용한다."
    )


def test_blt04_missing():
    fs = check_bytes(_skeleton_with(NORMREF[1], None), rules="BLT-04").findings
    assert ids(fs) == ["BLT-04"] and "없습니다" in fs[0].message


# ── VRB-01·VRB-02 ──
def test_vrb01_must():
    fs = run(["측정 전에는 반드시 영점 조정을 하여야 한다."], "VRB-01")
    assert ids(fs) == ["VRB-01"] and not fs[0].fix.auto
    assert fs[0].suggestion == "측정 전에는 영점 조정을 하여야 한다."


def test_vrb02_candidates_and_trap8_boilerplate():
    body = [
        "이 표준의 다른 시험들은 편리한 순서에 따라 수행할 수 있다.",
        "이 표준의 내용 일부 또는 전부는 저작권법에 따른 보호대상이 되는 저작물이 될 수 있다.",
        "인가할 수 있는 최대 전압",
    ]
    fs = run(body, "VRB-02")
    assert len(fs) == 1 and fs[0].severity == "info" and "수행할 수 있다" in fs[0].snippet
