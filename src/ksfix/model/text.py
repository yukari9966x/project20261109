"""보이는 텍스트 추출과 텍스트↔런 매핑.

- w:t만 모으고 w:delText·w:instrText와 필드 코드(fldChar begin~separate)는 뺀다.
- 필드 결과(separate~end)는 보이는 텍스트에 넣되 자동 수정 금지 구역으로 표시한다.
- 필드 상태는 문단을 넘어 이어진다(목차 TOC 필드 등) → FieldTracker를 문서 전체에서 공유한다.
- w:hyperlink·w:sdtContent·w:ins 안의 런은 포함한다(기존 w:ins 안은 수정 금지).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ksfix.model.ir import OBJ, Span
from ksfix.model.ns import M_NS, MC_NS, W_NS, local, ns_of, w, wattr

# Symbol 글꼴 문자(w:sym) → 유니코드(자주 쓰는 것만)
SYM_MAP = {
    "F0B1": "±",
    "F0B4": "×",
    "F0B0": "°",
    "F0A3": "≤",
    "F0B3": "≥",
    "F06D": "μ",
    "F057": "Ω",
    "F0BB": "≈",
    "F0B9": "≠",
    "F02D": "−",
    "F0D7": "·",
    "F0AE": "→",
    "F0E6": "(",
    "F0F6": ")",
    "F0A2": "′",
    "F0B2": "″",
    "F0A5": "∞",
    "F0B6": "∂",
    "F0D6": "√",
    "F0E5": "∑",
    "F0C5": "⊕",
    "F044": "Δ",
    "F064": "δ",
    "F061": "α",
    "F062": "β",
    "F067": "γ",
    "F06C": "λ",
    "F070": "π",
    "F073": "σ",
    "F074": "τ",
    "F066": "φ",
    "F077": "ω",
    "F0D8": "¬",
}

# 문단 안에서 들어가 볼 묶음 요소
_CONTAINERS = {"hyperlink", "ins", "moveTo", "smartTag", "customXml", "fldSimple", "sdt"}
# 수정해도 되는 묶음(같은 묶음 안에서만)
_EDITABLE_CONTAINERS = {"hyperlink", "sdtContent", "smartTag", "customXml"}
_OBJECT_TAGS = {"drawing", "pict", "object", "footnoteReference", "endnoteReference", "ruby"}


@dataclass
class _Field:
    state: str = "code"  # "code" | "result"
    instr: str = ""


@dataclass
class FieldTracker:
    """fldChar begin/separate/end 상태 기계(문서 전체 공유)."""

    stack: list[_Field] = field(default_factory=list)

    def begin(self) -> None:
        self.stack.append(_Field())

    def separate(self) -> None:
        if self.stack:
            self.stack[-1].state = "result"

    def end(self) -> str | None:
        if self.stack:
            return self.stack.pop().instr
        return None

    def add_instr(self, text: str) -> None:
        if self.stack and self.stack[-1].state == "code":
            self.stack[-1].instr += text

    @property
    def hidden(self) -> bool:
        """필드 코드 부분이면 보이지 않는다."""
        return any(f.state == "code" for f in self.stack)

    @property
    def in_field(self) -> bool:
        return bool(self.stack)

    def instrs(self) -> list[str]:
        return [f.instr.strip() for f in self.stack]

    @property
    def in_toc(self) -> bool:
        return any(f.instr.strip().upper().startswith("TOC") for f in self.stack)


@dataclass
class ParaText:
    text: str
    spans: list[Span]
    has_field: bool = False
    has_drawing: bool = False
    has_math: bool = False
    in_toc: bool = False
    fields: list[str] = field(default_factory=list)  # 이 문단에서 끝난 필드의 명령
    has_ins_del: bool = False


def _run_is_hidden(run: Any) -> bool:
    rpr = run.find(w("rPr"))
    if rpr is None:
        return False
    v = rpr.find(w("vanish"))
    if v is None:
        return False
    val = wattr(v, "val")
    return val is None or val.lower() not in ("0", "false", "off")


def _run_is_splittable(run: Any) -> bool:
    """w:t가 정확히 하나이고 필드·개체가 없는 런만 분할 편집 대상."""
    n_t = 0
    for c in run:
        tag = local(c.tag)
        if ns_of(c.tag) == W_NS and tag == "t":
            n_t += 1
        elif tag in ("rPr", "lastRenderedPageBreak"):
            continue
        else:
            return False
    return n_t == 1


class _Extractor:
    def __init__(self, tracker: FieldTracker):
        self.tracker = tracker
        self.parts: list[str] = []
        self.spans: list[Span] = []
        self.pos = 0
        self.run_index = 0
        self.out = ParaText(text="", spans=[])

    def add(
        self,
        s: str,
        kind: str,
        run: Any,
        node: Any,
        editable: bool,
        container: Any,
        run_offset: int,
    ) -> None:
        if not s:
            return
        self.spans.append(
            Span(
                start=self.pos,
                end=self.pos + len(s),
                kind=kind,
                run=run,
                node=node,
                editable=editable,
                container=container,
                run_index=self.run_index,
                run_offset=run_offset,
                in_field=self.tracker.in_field,
            )
        )
        self.parts.append(s)
        self.pos += len(s)

    def walk(self, parent: Any, container: Any, ctx_editable: bool) -> None:
        for el in parent:
            tag = el.tag
            if not isinstance(tag, str):
                continue
            ns = ns_of(tag)
            name = local(tag)
            if ns == W_NS:
                if name == "r":
                    self.run(el, container, ctx_editable)
                elif name in ("del", "moveFrom"):
                    self.out.has_ins_del = True
                    continue
                elif name in _CONTAINERS:
                    if name in ("ins", "moveTo"):
                        self.out.has_ins_del = True
                    if name == "sdt":
                        content = el.find(w("sdtContent"))
                        if content is not None:
                            self.walk(content, content, ctx_editable)
                        continue
                    if name == "fldSimple":
                        self.out.has_field = True
                        self.tracker.stack.append(
                            _Field(state="result", instr=wattr(el, "instr") or "")
                        )
                        self.walk(el, el, False)
                        f = self.tracker.stack.pop()
                        self.out.fields.append(f.instr.strip())
                        continue
                    editable = ctx_editable and name in _EDITABLE_CONTAINERS
                    self.walk(el, el, editable)
            elif ns == M_NS and name in ("oMath", "oMathPara"):
                self.out.has_math = True
                if not self.tracker.hidden:
                    self.add(OBJ, "obj", el, el, False, container, 0)
            elif ns == MC_NS and name == "AlternateContent":
                choice = el.find(f"{{{MC_NS}}}Choice")
                if choice is not None:
                    self.walk(choice, container, False)

    def run(self, run: Any, container: Any, ctx_editable: bool) -> None:
        if _run_is_hidden(run):
            return
        splittable = _run_is_splittable(run)
        offset = 0
        for c in run:
            tag = c.tag
            if not isinstance(tag, str):
                continue
            ns = ns_of(tag)
            name = local(tag)
            if ns == W_NS and name == "fldChar":
                ftype = wattr(c, "fldCharType")
                self.out.has_field = True
                if ftype == "begin":
                    self.tracker.begin()
                elif ftype == "separate":
                    self.tracker.separate()
                elif ftype == "end":
                    instr = self.tracker.end()
                    if instr is not None:
                        self.out.fields.append(instr.strip())
                continue
            if ns == W_NS and name == "instrText":
                self.tracker.add_instr(c.text or "")
                continue
            if self.tracker.hidden:
                continue
            if self.tracker.in_toc:
                self.out.in_toc = True
            in_field = self.tracker.in_field
            if in_field:
                self.out.has_field = True
            editable = ctx_editable and splittable and not in_field
            if ns == W_NS:
                if name == "t":
                    s = c.text or ""
                    self.add(s, "t", run, c, editable, container, offset)
                    offset += len(s)
                elif name in ("tab", "ptab"):
                    self.add("\t", "tab", run, c, False, container, offset)
                    offset += 1
                elif name in ("br", "cr"):
                    self.add("\n", "br", run, c, False, container, offset)
                    offset += 1
                elif name == "noBreakHyphen":
                    self.add("‑", "nbh", run, c, False, container, offset)
                    offset += 1
                elif name == "sym":
                    code = (wattr(c, "char") or "").upper()
                    ch = SYM_MAP.get(code)
                    if ch is None and code:
                        try:
                            val = int(code, 16)
                            ch = chr(val - 0xF000) if 0xF020 <= val <= 0xF0FF else OBJ
                        except ValueError:
                            ch = OBJ
                    self.add(ch or OBJ, "sym", run, c, False, container, offset)
                    offset += 1
                elif name in _OBJECT_TAGS:
                    if name in ("drawing", "pict", "object"):
                        self.out.has_drawing = True
                    self.add(OBJ, "obj", run, c, False, container, offset)
                    offset += 1
            elif ns == MC_NS and name == "AlternateContent":
                self.out.has_drawing = True
                self.add(OBJ, "obj", run, c, False, container, offset)
                offset += 1
        self.run_index += 1


def extract(p: Any, tracker: FieldTracker | None = None) -> ParaText:
    """w:p 요소의 보이는 텍스트와 span 목록."""
    tracker = tracker if tracker is not None else FieldTracker()
    ex = _Extractor(tracker)
    in_toc_at_start = tracker.in_toc
    ex.walk(p, None, True)
    ex.out.text = "".join(ex.parts)
    ex.out.spans = ex.spans
    ex.out.in_toc = ex.out.in_toc or in_toc_at_start
    return ex.out


def offset_to_span(spans: list[Span], offset: int) -> Span | None:
    for s in spans:
        if s.start <= offset < s.end:
            return s
    return None
