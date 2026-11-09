from lxml import etree

from ksfix.fix.revisions import Revisions
from ksfix.fix.textedit import EditError, apply_text_edit, refresh, split_run, word_diff
from ksfix.model.ir import Para
from ksfix.model.ns import W_NS

NS = f'xmlns:w="{W_NS}"'


class FakeDoc:
    """Revisions가 쓰는 최소 인터페이스(part.package.iter_parts)."""

    class part:
        class package:
            @staticmethod
            def iter_parts():
                return []


def para(inner: str) -> Para:
    p = etree.fromstring(f"<w:p {NS}>{inner}</w:p>".encode())
    pa = Para(idx=0, xml=p, text="", spans=[], style_id=None, style_name=None)
    refresh(pa)
    return pa


def rev() -> Revisions:
    return Revisions(FakeDoc(), date="2026-11-10T00:00:00Z")


def tags(p: Para) -> list[str]:
    return [etree.QName(c).localname for c in p.xml]


def test_split_run_keeps_formatting():
    pa = para("<w:r><w:rPr><w:b/></w:rPr><w:t>abcdef</w:t></w:r>")
    left, right = split_run(pa.xml[0], 2)
    assert left.find(f"{{{W_NS}}}t").text == "ab"
    assert right.find(f"{{{W_NS}}}t").text == "cdef"
    assert right.find(f"{{{W_NS}}}rPr/{{{W_NS}}}b") is not None


def test_word_diff_minimal():
    assert word_diff("위해 필요하다.", "위해 필수적이다.") == [(4, 6, "수적이")]
    assert word_diff("150kg", "150 kg") == [(3, 3, " ")]


def test_tracked_replace_structure_and_accepted_text():
    pa = para("<w:r><w:rPr><w:i/></w:rPr><w:t>온도 5 ~ 40 ℃</w:t></w:r>")
    anchors = apply_text_edit(pa, 5, 6, "∼", "tracked", rev())
    assert pa.text == "온도 5 ∼ 40 ℃"  # 수락된 상태로 읽음
    assert tags(pa) == ["r", "del", "ins", "r"]
    d = pa.xml.find(f"{{{W_NS}}}del")
    assert d.find(f".//{{{W_NS}}}delText").text == "~"
    ins = pa.xml.find(f"{{{W_NS}}}ins")
    assert ins.find(f".//{{{W_NS}}}i") is not None  # 원래 서식 복사
    assert ins.get(f"{{{W_NS}}}author") == "KS-Fix"
    assert len(anchors) == 2


def test_clean_replace_and_insertion():
    pa = para("<w:r><w:t>최대 150kg</w:t></w:r>")
    apply_text_edit(pa, 6, 6, " ", "clean", None)
    assert pa.text == "최대 150 kg"
    assert pa.xml.find(f".//{{{W_NS}}}ins") is None


def test_multiple_edits_right_to_left_and_multirun():
    pa = para("<w:r><w:t>그림</w:t></w:r><w:r><w:t>1. 구조</w:t></w:r>")
    apply_text_edit(pa, 0, len(pa.text), "그림 1 — 구조", "tracked", rev())
    assert pa.text == "그림 1 — 구조"


def test_field_result_refused():
    pa = para(
        "<w:r><w:t>표 </w:t></w:r><w:r><w:fldChar w:fldCharType='begin'/></w:r>"
        "<w:r><w:instrText>SEQ 표</w:instrText></w:r><w:r><w:fldChar w:fldCharType='separate'/></w:r>"
        "<w:r><w:t>1</w:t></w:r><w:r><w:fldChar w:fldCharType='end'/></w:r>"
    )
    try:
        apply_text_edit(pa, 2, 3, "2", "tracked", rev())
    except EditError:
        pass
    else:
        raise AssertionError("필드 결과는 수정하면 안 된다")
    assert pa.text == "표 1"


def test_revision_ids_unique():
    pa = para("<w:r><w:t>a ~ b ~ c</w:t></w:r>")
    r = rev()
    apply_text_edit(pa, 6, 7, "∼", "tracked", r)
    apply_text_edit(pa, 2, 3, "∼", "tracked", r)
    ids = [
        el.get(f"{{{W_NS}}}id")
        for el in pa.xml.iter()
        if etree.QName(el).localname in ("ins", "del")
    ]
    assert len(ids) == len(set(ids)) == 4
