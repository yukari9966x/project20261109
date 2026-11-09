from lxml import etree

from ksfix.model.numbering import Numbering, NumberingState, format_number

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
NUMBERING = f"""<w:numbering {W}>
 <w:abstractNum w:abstractNumId="1">
  <w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1 "/></w:lvl>
  <w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1.%2"/></w:lvl>
  <w:lvl w:ilvl="2"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1.%2.%3"/></w:lvl>
 </w:abstractNum>
 <w:abstractNum w:abstractNumId="2">
  <w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="upperLetter"/><w:pStyle w:val="AnnexA"/><w:lvlText w:val="부속서&#160;%1"/></w:lvl>
  <w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:pStyle w:val="AnnexA1"/><w:lvlText w:val="%1.%2 "/></w:lvl>
 </w:abstractNum>
 <w:abstractNum w:abstractNumId="3">
  <w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="lowerLetter"/><w:lvlText w:val="%1)"/></w:lvl>
 </w:abstractNum>
 <w:abstractNum w:abstractNumId="4">
  <w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="비고"/></w:lvl>
  <w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="&#xF0B7;"/></w:lvl>
 </w:abstractNum>
 <w:num w:numId="1"><w:abstractNumId w:val="1"/></w:num>
 <w:num w:numId="2"><w:abstractNumId w:val="2"/></w:num>
 <w:num w:numId="3"><w:abstractNumId w:val="3"/></w:num>
 <w:num w:numId="4"><w:abstractNumId w:val="1"/><w:lvlOverride w:ilvl="0"><w:startOverride w:val="8"/></w:lvlOverride></w:num>
 <w:num w:numId="5"><w:abstractNumId w:val="4"/></w:num>
</w:numbering>"""


def state() -> NumberingState:
    return NumberingState(Numbering(etree.fromstring(NUMBERING.encode())))


def test_multilevel_and_reset():
    s = state()
    seq = [s.next_label("1", lv) for lv in (0, 1, 1, 2, 0, 1)]
    assert seq == ["1", "1.1", "1.2", "1.2.1", "2", "2.1"]


def test_annex_letters_use_upper_letter_in_sublevels():
    s = state()
    seq = [s.next_label("2", lv) for lv in (0, 1, 1, 0, 1)]
    assert seq == ["부속서 A", "A.1", "A.2", "부속서 B", "B.1"]


def test_start_override_restarts_list():
    s = state()
    assert [s.next_label("1", 0) for _ in range(3)] == ["1", "2", "3"]
    assert s.next_label("4", 0) == "8"


def test_level_for_style_uses_pstyle_link():
    n = Numbering(etree.fromstring(NUMBERING.encode()))
    assert n.level_for_style("2", "AnnexA") == 0
    assert n.level_for_style("2", "AnnexA1") == 1
    assert n.level_for_style("2", "Other") is None


def test_literal_label_and_bullet():
    s = state()
    assert s.next_label("5", 0) == "비고"
    assert s.next_label("5", 1) == "•"


def test_unknown_or_removed_numbering():
    s = state()
    assert s.next_label("0", 0) is None
    assert s.next_label("99", 0) is None
    assert s.next_label(None, 0) is None


def test_separate_abstracts_count_independently():
    s = state()
    assert s.next_label("3", 0) == "a)"
    assert s.next_label("1", 0) == "1"
    assert s.next_label("3", 0) == "b)"


def test_format_number():
    assert format_number(27, "upperLetter") == "AA"
    assert format_number(4, "lowerRoman") == "iv"
    assert format_number(14, "upperRoman") == "XIV"
    assert format_number(2, "ganada") == "나"
    assert format_number(3, "decimalEnclosedCircle") == "③"
    assert format_number(5, "none") == ""
    assert format_number(7, "unknownFormat") == "7"
