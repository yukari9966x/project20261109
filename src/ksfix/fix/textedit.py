"""텍스트 편집: 보이는 텍스트 오프셋 → 런 분할 → w:del/w:ins(변경추적) 또는 직접 반영(clean).

- 편집 전에 문단의 span을 새로 계산한다(앞선 편집으로 런이 나뉘었을 수 있음).
- 교체는 단어 단위 최소 차이로 쪼개 변경 표시를 작게 남긴다.
"""

from __future__ import annotations

import copy
import difflib
import re
from typing import Any

from lxml import etree

from ksfix.fix.revisions import Revisions
from ksfix.model.ir import Para, Span
from ksfix.model.ns import XML_NS, w
from ksfix.model.text import FieldTracker, extract


class EditError(RuntimeError):
    """안전하게 편집할 수 없는 구간."""


def refresh(para: Para) -> None:
    pt = extract(para.xml, FieldTracker())
    para.text = pt.text
    para.spans = pt.spans


def _t(run: Any) -> Any:
    return run.find(w("t"))


def _set_text(t_el: Any, text: str) -> None:
    t_el.text = text
    t_el.set(f"{{{XML_NS}}}space", "preserve")


ONE_CHAR = {w("tab"), w("br"), w("cr"), w("noBreakHyphen")}


def _child_len(c: Any) -> int:
    if c.tag == w("t"):
        return len(c.text or "")
    return 1 if c.tag in ONE_CHAR else 0


def run_length(run: Any) -> int:
    return sum(_child_len(c) for c in run if c.tag != w("rPr"))


def split_run(run: Any, k: int) -> tuple[Any, Any]:
    """런을 보이는 글자 k번째에서 둘로 나눈다(w:t·탭·줄바꿈이 섞인 런도 처리, 서식 복사)."""
    total = run_length(run)
    if not 0 < k < total:
        raise EditError("런 분할 위치가 범위를 벗어났습니다.")
    right = etree.Element(w("r"))
    rpr = run.find(w("rPr"))
    if rpr is not None:
        right.append(copy.deepcopy(rpr))
    pos = 0
    moving = False
    for c in [c for c in run if c.tag != w("rPr")]:
        n = _child_len(c)
        if moving:
            right.append(c)  # 이후 자식은 오른쪽 런으로 옮긴다
            continue
        if pos + n <= k:
            pos += n
            if pos == k:
                moving = True
            continue
        # 이 자식 안에서 나눈다(w:t만 길이가 2 이상)
        cut = k - pos
        text = c.text or ""
        t2 = etree.SubElement(right, w("t"))
        _set_text(t2, text[cut:])
        _set_text(c, text[:cut])
        moving = True
        pos = k
    run.addnext(right)
    return run, right


def _editable_spans(para: Para, start: int, end: int) -> list[Span]:
    spans = para.spans_in(start, end)
    if not spans or not para.is_editable(start, end):
        raise EditError("수정 금지 구역(필드·기존 변경추적·여러 w:t 런 등)입니다.")
    return spans


def isolate(para: Para, start: int, end: int) -> list[Any]:
    """[start, end)를 정확히 덮는 런 목록(필요하면 런을 나눈다)."""
    runs = []
    for s in _editable_spans(para, start, end):
        run = s.run
        a = s.run_offset + max(start, s.start) - s.start
        b = s.run_offset + min(end, s.end) - s.start
        if b < run_length(run):
            run, _ = split_run(run, b)
        if a > 0:
            _, run = split_run(run, a)
        runs.append(run)
    return runs


def make_run(text: str, rpr: Any | None) -> Any:
    run = etree.Element(w("r"))
    if rpr is not None:
        run.append(copy.deepcopy(rpr))
    parts = re.split(r"(\t)", text)
    for part in parts:
        if not part:
            continue
        if part == "\t":
            run.append(etree.Element(w("tab")))
        else:
            t_el = etree.SubElement(run, w("t"))
            _set_text(t_el, part)
    return run


def _rpr(run: Any) -> Any | None:
    return run.find(w("rPr"))


def _wrap(tag: str, el: Any, rev: Revisions) -> Any:
    wrapper = etree.Element(w(tag), rev.attrs())
    el.addprevious(wrapper)
    wrapper.append(el)
    return wrapper


def _to_deltext(run: Any) -> None:
    for t_el in run.findall(w("t")):
        t_el.tag = w("delText")
        t_el.set(f"{{{XML_NS}}}space", "preserve")


def low_level_replace(
    para: Para, start: int, end: int, new: str, mode: str, rev: Revisions | None
) -> list[Any]:
    """[start, end) → new. 반환: 메모를 달 요소(삽입 런 또는 삭제 묶음)."""
    refresh(para)
    if start == end:
        if not new:
            return []
        span = _insertion_span(para, start)
        run = span.run
        k = span.run_offset + start - span.start
        length = run_length(run)
        new_run = make_run(new, _rpr(run))
        if k == 0:
            anchor_before = run
            if mode == "tracked":
                ins = etree.Element(w("ins"), rev.attrs())
                ins.append(new_run)
                anchor_before.addprevious(ins)
                return [ins]
            anchor_before.addprevious(new_run)
            return [new_run]
        if k < length:
            run, _ = split_run(run, k)
        if mode == "tracked":
            ins = etree.Element(w("ins"), rev.attrs())
            ins.append(new_run)
            run.addnext(ins)
            return [ins]
        run.addnext(new_run)
        return [new_run]

    runs = isolate(para, start, end)
    rpr = _rpr(runs[0])
    anchors: list[Any] = []
    if mode == "tracked":
        last = None
        for r in runs:
            _to_deltext(r)
            last = _wrap("del", r, rev)
            anchors.append(last)
        if new:
            ins = etree.Element(w("ins"), rev.attrs())
            ins.append(make_run(new, rpr))
            last.addnext(ins)
            anchors = [anchors[0], ins]
        return anchors
    first = runs[0]
    if new:
        new_run = make_run(new, rpr)
        first.addprevious(new_run)
        anchors = [new_run]
    else:
        prev = first.getprevious()
        anchors = [prev] if prev is not None else []
    for r in runs:
        r.getparent().remove(r)
    return anchors


def _insertion_span(para: Para, pos: int) -> Span:
    cands = [s for s in para.spans if s.kind == "t" and s.editable and s.start <= pos <= s.end]
    if not cands:
        raise EditError("삽입 위치가 수정 금지 구역입니다.")
    for s in cands:  # 앞 글자 런 뒤에 붙이는 것을 우선(서식 이어받기)
        if s.end == pos and s.end > s.start:
            return s
    return cands[0]


TOKEN_RE = re.compile(r"\s+|[^\s]+")


def word_diff(old: str, new: str) -> list[tuple[int, int, str]]:
    """old 기준 (시작, 끝, 대체 문자열) 목록 — 단어(공백 포함 토큰) 단위 최소 차이."""
    a = TOKEN_RE.findall(old)
    b = TOKEN_RE.findall(new)
    offsets = [0]
    for tok in a:
        offsets.append(offsets[-1] + len(tok))
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    edits = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        start, end = offsets[i1], offsets[i2]
        repl = "".join(b[j1:j2])
        edits.extend(_refine(old[start:end], repl, start))
    return edits


def _refine(old: str, new: str, base: int) -> list[tuple[int, int, str]]:
    """토큰 교체 안에서 공통 앞뒤 글자를 덜어 낸다("필요하다"→"필수적이다": "요하"→"수적이")."""
    p = 0
    while p < min(len(old), len(new)) and old[p] == new[p]:
        p += 1
    s = 0
    while s < min(len(old), len(new)) - p and old[len(old) - 1 - s] == new[len(new) - 1 - s]:
        s += 1
    o2, n2 = old[p : len(old) - s], new[p : len(new) - s]
    if not o2 and not n2:
        return []
    return [(base + p, base + p + len(o2), n2)]


def apply_text_edit(
    para: Para, start: int, end: int, new_text: str, mode: str, rev: Revisions | None
) -> list[Any]:
    """[start, end)를 new_text로: 최소 차이 편집을 뒤에서부터 적용. 반환: 메모 앵커 요소들."""
    old = para.text[start:end]
    if old == new_text:
        return []
    subs = word_diff(old, new_text) if old else [(0, 0, new_text)]
    anchors: list[Any] = []
    for a, b, repl in sorted(subs, key=lambda x: x[0], reverse=True):
        got = low_level_replace(para, start + a, start + b, repl, mode, rev)
        anchors = got + anchors
    refresh(para)
    return anchors


def simulate(text: str, edits: list[tuple[int, int, str]]) -> str:
    out = text
    for a, b, repl in sorted(edits, key=lambda x: x[0], reverse=True):
        out = out[:a] + repl + out[b:]
    return out
