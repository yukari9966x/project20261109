"""구조 인식·규칙에서 함께 쓰는 정규식과 텍스트 도우미."""

from __future__ import annotations

import re

from ksfix.model.ir import OBJ

SPACE_RE = re.compile(r"\s+")


def squash(text: str) -> str:
    """공백을 모두 지운다("머  리  말" → "머리말")."""
    return SPACE_RE.sub("", text.replace(OBJ, ""))


def clean(text: str) -> str:
    """앞뒤 공백·줄바꿈을 정리하고 연속 공백을 하나로."""
    return SPACE_RE.sub(" ", text.replace(OBJ, " ")).strip()


HANGUL_RE = re.compile(r"[가-힣]")
LATIN_RE = re.compile(r"[A-Za-z]")


def hangul_ratio(text: str) -> float:
    h = len(HANGUL_RE.findall(text))
    latin = len(LATIN_RE.findall(text))
    return h / (h + latin) if (h + latin) else 0.0


# 표준번호: KS X 9999:2026, KS C IEC 60974-11:2021, KS X ISO/IEC 27001, ISO 9001:2015 …
STD_NO_CORE = (
    r"(?:KS\s?[A-Z](?:\s+(?:ISO/IEC|ISO|IEC|ITU-T|IEEE))?|ISO/IEC|ISO|IEC|ASTM|EN|JIS\s?[A-Z]?|"
    r"ANSI|DIN|BS|IEEE|ITU-T|OIML\s+[RD]|IEC\s+Guide|ISO\s+Guide|ISO/IEC\s+Guide)"
    r"\s?[A-Z]?\s?\d[\d.\-]*(?:[-/]\d+)*"
)
STD_NO_RE = re.compile(rf"(?<![A-Za-z]){STD_NO_CORE}(?:\s*[:：]\s*(?:19|20)\d\d)?")
STD_NUMBER_LINE_RE = re.compile(
    r"^KS\s?[A-Z](?:\s+(?:ISO/IEC|ISO|IEC))?\s+[0-9A-Z][\d\-]*(?:\s*[:：]\s*\d{4})?$"
)

NOTE_RE = re.compile(r"^비\s?고(\s*\d+)?(?=\s|$|[:：])")
EXAMPLE_RE = re.compile(r"^보\s?기(\s*\d+)?(?=\s|$|[:：])")
REMARK_RE = re.compile(r"^참\s?고(\s*\d+)?(?=\s|$|[:：])")

# 캡션: "표 1 — 제목", "그림 A.2 — 제목", "그림1. 구조", "<표 1> 측정 범위"
CAPTION_RE = re.compile(
    r"^(?:<\s*)?(?P<kind>표|그림)\s*(?P<num>(?:[A-Z]\.)?\d+)(?:\s*>)?"
    r"(?P<rest>(?:\s*[—–\-:.．]\s*|\s+|\(계속\)|$).*)$",
    re.S,
)
# 번호 뒤에 조사가 오면 본문 문장("표 2를 참조한다")이다.
PARTICLE_AFTER_NUM_RE = re.compile(r"^(?:\s*(?:\(계속\))?)?[을를에의은는과와로이가도만]")

TERM_SOURCE_RE = re.compile(r"^\[\s*(?:출처|SOURCE)\s*[:：]", re.I)
BIBLIO_ENTRY_RE = re.compile(r"^\[\d+\]")
UNIT_LABEL_RE = re.compile(r"^단위\s*[:：]")
ANNEX_TEXT_RE = re.compile(r"^부속서\s*(?P<letter>[A-Z])(?=\s|$|\(|\n)")
ANNEX_STATUS_RE = re.compile(r"^\(\s*(?P<status>규정|참고)\s*\)$")
TYPED_HEADING_RE = re.compile(r"^(?P<num>\d{1,2}(?:\.\d{1,3}){0,6})[ \t ]+(?P<title>\S.*)$", re.S)
TYPED_ANNEX_CLAUSE_RE = re.compile(
    r"^(?P<num>[A-Z]\.\d{1,3}(?:\.\d{1,3}){0,5})[ \t ]+(?P<title>\S.*)$", re.S
)
TERM_NUMBER_RE = re.compile(r"^\d{1,2}(?:\.\d{1,3}){1,5}$")
LIST_TEXT_RE = re.compile(r"^(?:[a-z]\)|\d{1,2}\)|[—–•·▪●○■□➢✓◦]|-(?=[\s\t]))[\s\t]*\S")
LIST_LABEL_RE = re.compile(r"^(?:[a-z]\)|\d{1,2}\)|[—–\-•·▪●○■□➢✓◦]|[①-⑳])$")
TOC_PAGE_RE = re.compile(r"(?:\t|[.·…]{3,}|\s{2,})\s*(?:\d{1,3}|[ivxlc]{1,6})$", re.I)
SENTENCE_END_RE = re.compile(r"(?:다|요|음|함|것|임)\s*[.。]?\s*$|[.。]\s*$")
FORMULA_REST_RE = re.compile(r"^\s*(?:\(\s*(?:[A-Z]\.)?\d+[a-z]?\s*\))?\s*$")


def is_sentence(text: str) -> bool:
    return bool(SENTENCE_END_RE.search(text.strip()))


def caption_match(text: str) -> re.Match[str] | None:
    """캡션 꼴이면 match. 본문 문장("표 2를 참조한다.")·목차 항목은 제외."""
    t = text.strip()
    if not t or len(t) > 150:
        return None
    m = CAPTION_RE.match(t)
    if not m:
        return None
    rest = m.group("rest")
    if PARTICLE_AFTER_NUM_RE.match(rest):
        return None
    if TOC_PAGE_RE.search(t):
        return None
    body = rest.strip(" —–-:.．")
    if body.endswith(("다.", "다", "참조.", "참조")) and len(body) > 0 and "—" not in rest:
        return None
    return m
