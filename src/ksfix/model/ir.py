"""문서 모델(IR): docx를 규칙 엔진이 다루기 쉬운 블록·런 구조로 표현한다."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Role(StrEnum):
    COVER = "cover"
    COVER_INFO = "cover_info"
    BACK_COVER = "back_cover"
    TOC_TITLE = "toc_title"
    TOC_ENTRY = "toc_entry"
    FOREWORD_TITLE = "foreword_title"
    FOREWORD = "foreword"
    INTRO_TITLE = "intro_title"
    INTRO = "intro"
    STD_NUMBER = "std_number"
    TITLE_KO = "title_ko"
    TITLE_EN = "title_en"
    HEADING = "heading"  # attrs: level·number·title
    BODY = "body"
    LIST_ITEM = "list_item"
    NOTE = "note"  # 비고
    EXAMPLE = "example"  # 보기
    REMARK = "remark"  # 참고
    TABLE_CAPTION = "table_caption"
    TABLE_CELL = "table_cell"
    FIGURE = "figure"
    FIGURE_CAPTION = "figure_caption"
    UNIT_LABEL = "unit_label"
    FORMULA = "formula"
    NORMREF_INTRO = "normref_intro"
    NORMREF_ENTRY = "normref_entry"
    TERMS_INTRO = "terms_intro"
    TERM_NUMBER = "term_number"
    TERM = "term"
    DEFINITION = "definition"
    TERM_SOURCE = "term_source"
    ANNEX_HEADING = "annex_heading"
    ANNEX_STATUS = "annex_status"
    ANNEX_TITLE = "annex_title"
    BIBLIO_TITLE = "biblio_title"
    BIBLIO_ENTRY = "biblio_entry"
    COMMENTARY_TITLE = "commentary_title"
    COMMENTARY = "commentary"
    EMPTY = "empty"
    UNKNOWN = "unknown"


# 보이는 텍스트에서 그림·수식·각주 표시 등 문자가 아닌 개체를 나타내는 자리표시 문자
OBJ = "￼"


@dataclass
class Span:
    """보이는 텍스트 구간 [start, end) ↔ 원본 XML 노드."""

    start: int
    end: int
    kind: str  # "t" | "tab" | "br" | "sym" | "obj" | "nbh"
    run: Any  # lxml w:r (또는 m:oMath 같은 개체 요소)
    node: Any  # w:t·w:tab 등 실제 노드
    editable: bool  # 자동 수정 가능 여부(안전 구역이면 False)
    container: Any = None  # 문단 안의 가장 가까운 묶음 요소(w:hyperlink·w:ins·w:sdtContent 등)
    run_index: int = 0
    run_offset: int = 0
    in_field: bool = False


@dataclass
class Para:
    idx: int  # 문서 전체 문단 순번(표 안 문단 포함, 안정 ID)
    xml: Any  # lxml w:p 요소
    text: str  # 보이는 텍스트: 삭제 텍스트·필드 코드 제외, 필드 결과 포함
    spans: list[Span]
    style_id: str | None
    style_name: str | None
    num_label: str | None = None  # 자동번호 렌더링 결과: "5.1", "부속서 A", "a)"
    num_level: int | None = None
    num_id: str | None = None
    section_idx: int = 0
    in_table: bool = False
    table_idx: int | None = None
    cell: tuple[int, int] | None = None  # (행, 열)
    has_drawing: bool = False
    has_field: bool = False
    has_math: bool = False
    role: Role = Role.UNKNOWN
    role_conf: float = 0.0
    clause_no: str | None = None  # 소속 절·항 번호(트리 구성 후)
    attrs: dict = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        """자동번호 라벨을 포함한 보이는 텍스트."""
        if self.num_label:
            return f"{self.num_label} {self.text}".strip()
        return self.text

    def spans_in(self, start: int, end: int) -> list[Span]:
        return [s for s in self.spans if s.end > start and s.start < end]

    def is_editable(self, start: int, end: int) -> bool:
        """[start, end) 구간을 런 분할로 안전하게 고칠 수 있는지."""
        if start < 0 or end > len(self.text) or start > end:
            return False
        if start == end:
            # 삽입: 앞 또는 뒤 글자가 편집 가능한 span 안에 있어야 한다.
            for s in self.spans:
                if s.kind == "t" and s.editable and s.start <= start <= s.end:
                    return True
            return False
        spans = self.spans_in(start, end)
        if not spans:
            return False
        containers = {id(s.container) for s in spans}
        if len(containers) > 1:
            return False
        return all(s.kind == "t" and s.editable for s in spans)

    def __repr__(self) -> str:  # lxml 요소를 출력하지 않는다
        return (
            f"Para(idx={self.idx}, role={self.role.value}, style={self.style_name!r}, "
            f"label={self.num_label!r}, text={self.text[:40]!r})"
        )


@dataclass
class Table:
    idx: int
    xml: Any
    cells: list[list[list[Para]]]  # 행 → 열 → 셀 안 문단
    nested: bool
    section_idx: int
    in_table: bool = False  # 다른 표 안에 들어 있는 표인지

    @property
    def paras(self) -> list[Para]:
        return [p for row in self.cells for cell in row for p in cell]

    def __repr__(self) -> str:
        rows = len(self.cells)
        cols = max((len(r) for r in self.cells), default=0)
        return f"Table(idx={self.idx}, {rows}x{cols}, nested={self.nested})"


@dataclass
class KSDoc:
    blocks: list[Para | Table]
    paras: list[Para] = field(default_factory=list)  # 모든 문단(표 안 포함), 문서 순서
    tables: list[Table] = field(default_factory=list)
    meta: dict = field(default_factory=dict)
    tree: Any = None
    docx: Any = field(default=None, repr=False)  # python-docx Document
    styles: Any = field(default=None, repr=False)
    numbering: Any = field(default=None, repr=False)

    def para(self, idx: int) -> Para:
        return self.paras[idx]

    def body_paras(self) -> list[Para]:
        """표 밖 문단."""
        return [p for p in self.paras if not p.in_table]

    def by_role(self, *roles: Role) -> list[Para]:
        want = set(roles)
        return [p for p in self.paras if p.role in want]
