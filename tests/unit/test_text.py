from lxml import etree

from ksfix.model.ir import OBJ, Para
from ksfix.model.text import FieldTracker, extract

NS = (
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"'
)


def P(inner: str):
    return etree.fromstring(f"<w:p {NS}>{inner}</w:p>".encode())


def fld(kind: str) -> str:
    return f'<w:r><w:fldChar w:fldCharType="{kind}"/></w:r>'


def para(pt) -> Para:
    return Para(idx=0, xml=None, text=pt.text, spans=pt.spans, style_id=None, style_name=None)


def test_field_result_visible_but_not_editable():
    p = P(
        "<w:r><w:t xml:space='preserve'>표 </w:t></w:r>"
        + fld("begin")
        + "<w:r><w:instrText> SEQ 표 \\* ARABIC </w:instrText></w:r>"
        + fld("separate")
        + "<w:r><w:t>1</w:t></w:r>"
        + fld("end")
        + "<w:r><w:t xml:space='preserve'> — 제목</w:t></w:r>"
    )
    pt = extract(p)
    assert pt.text == "표 1 — 제목"
    assert pt.has_field
    assert any(f.startswith("SEQ") for f in pt.fields)
    pa = para(pt)
    assert pa.is_editable(0, 1)  # "표"
    assert not pa.is_editable(2, 3)  # 필드 결과 "1"
    assert pa.is_editable(4, 5)  # "—"


def test_deleted_text_and_field_code_excluded():
    p = P(
        "<w:r><w:t>가</w:t></w:r>"
        "<w:del w:id='1' w:author='x'><w:r><w:delText>삭제</w:delText></w:r></w:del>"
        "<w:ins w:id='2' w:author='x'><w:r><w:t>삽입</w:t></w:r></w:ins>"
        "<w:r><w:t>나</w:t></w:r>"
    )
    pt = extract(p)
    assert pt.text == "가삽입나"
    assert pt.has_ins_del
    pa = para(pt)
    assert not pa.is_editable(1, 3)  # 기존 w:ins 안은 수정 금지
    assert pa.is_editable(0, 1)


def test_hyperlink_editable_inside_but_not_across_boundary():
    p = P(
        "<w:r><w:t>앞</w:t></w:r>"
        "<w:hyperlink><w:r><w:t>링크</w:t></w:r></w:hyperlink>"
        "<w:r><w:t>뒤</w:t></w:r>"
    )
    pa = para(extract(p))
    assert pa.text == "앞링크뒤"
    assert pa.is_editable(1, 3)
    assert not pa.is_editable(0, 2)


def test_tabs_breaks_symbols_and_math():
    p = P(
        "<w:r><w:t>a</w:t><w:tab/><w:t>b</w:t><w:br/></w:r>"
        "<w:r><w:sym w:font='Symbol' w:char='F0B1'/></w:r>"
        "<m:oMath><m:r><m:t>x</m:t></m:r></m:oMath>"
    )
    pt = extract(p)
    assert pt.text == "a\tb\n±" + OBJ
    assert pt.has_math
    pa = para(pt)
    assert not pa.is_editable(0, 1)  # w:t가 여러 개인 런은 분할하지 않는다


def test_field_state_crosses_paragraphs_toc():
    tr = FieldTracker()
    p1 = P(
        fld("begin")
        + '<w:r><w:instrText> TOC \\o "1-2" </w:instrText></w:r>'
        + fld("separate")
        + "<w:r><w:t>1 적용범위</w:t></w:r>"
    )
    p2 = P("<w:r><w:t>2 인용표준</w:t></w:r>")
    p3 = P("<w:r><w:t>3 용어</w:t></w:r>" + fld("end"))
    p4 = P("<w:r><w:t>본문</w:t></w:r>")
    r1, r2, r3, r4 = (extract(p, tr) for p in (p1, p2, p3, p4))
    assert r1.in_toc and r2.in_toc and r3.in_toc and not r4.in_toc
    assert not para(r2).is_editable(0, 1)
    assert para(r4).is_editable(0, 1)


def test_nested_field_inside_code_is_hidden():
    p = P(
        fld("begin")
        + "<w:r><w:instrText>IF </w:instrText></w:r>"
        + fld("begin")
        + "<w:r><w:instrText>DOCPROPERTY X</w:instrText></w:r>"
        + fld("separate")
        + "<w:r><w:t>숨김</w:t></w:r>"
        + fld("end")
        + "<w:r><w:instrText> = 1 </w:instrText></w:r>"
        + fld("separate")
        + "<w:r><w:t>보임</w:t></w:r>"
        + fld("end")
    )
    assert extract(p).text == "보임"


def test_hidden_run_and_drawing():
    p = P(
        "<w:r><w:rPr><w:vanish/></w:rPr><w:t>숨김</w:t></w:r>"
        "<w:r><w:drawing/></w:r>"
        "<w:r><w:t>그림</w:t></w:r>"
    )
    pt = extract(p)
    assert pt.text == OBJ + "그림"
    assert pt.has_drawing
