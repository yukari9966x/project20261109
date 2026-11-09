"""자동번호 해석: numbering.xml + 스타일 상속 체인 → 렌더링된 번호 라벨("5.1", "부속서 A", "a)")."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ksfix.model.ns import child, child_val, w, wattr

BULLET_MAP = {
    "": "•",
    "": "▪",
    "": "●",
    "": "■",
    "": "□",
    "": "➢",
    "": "✓",
    "": "-",
}

GANADA = "가나다라마바사아자차카타파하"
CHOSUNG = "ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ"


@dataclass
class Level:
    ilvl: int
    start: int
    fmt: str
    text: str
    pstyle: str | None
    restart: int | None
    is_lgl: bool


def _to_letters(n: int) -> str:
    # Word 방식: A..Z, AA..ZZ, AAA..
    if n <= 0:
        return ""
    k = (n - 1) // 26 + 1
    ch = chr(ord("A") + (n - 1) % 26)
    return ch * k


def _to_roman(n: int) -> str:
    if n <= 0:
        return str(n)
    vals = [
        (1000, "M"),
        (900, "CM"),
        (500, "D"),
        (400, "CD"),
        (100, "C"),
        (90, "XC"),
        (50, "L"),
        (40, "XL"),
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    ]
    out = []
    for v, s in vals:
        while n >= v:
            out.append(s)
            n -= v
    return "".join(out)


def format_number(n: int, fmt: str) -> str:
    if fmt in ("decimal", "decimalHalfWidth"):
        return str(n)
    if fmt == "decimalZero":
        return f"{n:02d}"
    if fmt == "upperLetter":
        return _to_letters(n)
    if fmt == "lowerLetter":
        return _to_letters(n).lower()
    if fmt == "upperRoman":
        return _to_roman(n)
    if fmt == "lowerRoman":
        return _to_roman(n).lower()
    if fmt == "none":
        return ""
    if fmt == "ganada":
        return GANADA[(n - 1) % len(GANADA)] if n > 0 else str(n)
    if fmt == "chosung":
        return CHOSUNG[(n - 1) % len(CHOSUNG)] if n > 0 else str(n)
    if fmt in ("decimalEnclosedCircle", "decimalEnclosedCircleChinese"):
        return chr(0x2460 + n - 1) if 1 <= n <= 20 else str(n)
    if fmt == "decimalEnclosedParen":
        return f"({n})"
    if fmt == "decimalEnclosedFullstop":
        return f"{n}."
    if fmt == "decimalFullWidth":
        return "".join(chr(0xFF10 + int(d)) for d in str(n))
    return str(n)


def _int(val: str | None, default: int | None = None) -> int | None:
    try:
        return int(val) if val is not None else default
    except ValueError:
        return default


def _parse_level(lvl: Any) -> Level:
    return Level(
        ilvl=_int(wattr(lvl, "ilvl"), 0) or 0,
        start=_int(child_val(lvl, "start"), 1) or 0,
        fmt=child_val(lvl, "numFmt") or "decimal",
        text=child_val(lvl, "lvlText") or "",
        pstyle=child_val(lvl, "pStyle"),
        restart=_int(child_val(lvl, "lvlRestart")),
        is_lgl=child(lvl, "isLgl") is not None,
    )


@dataclass
class _Override:
    start: int | None
    level: Level | None


class Numbering:
    """numbering.xml 정의."""

    def __init__(self, numbering_el: Any | None, styles: Any | None = None):
        self.abstract: dict[str, dict[int, Level]] = {}
        self.abstract_style_link: dict[str, str] = {}
        self.nums: dict[str, tuple[str, dict[int, _Override]]] = {}
        if numbering_el is None:
            return
        for a in numbering_el.findall(w("abstractNum")):
            aid = wattr(a, "abstractNumId")
            if aid is None:
                continue
            self.abstract[aid] = {
                lv.ilvl: lv for lv in (_parse_level(x) for x in a.findall(w("lvl")))
            }
            link = child_val(a, "numStyleLink")
            if link:
                self.abstract_style_link[aid] = link
        for n in numbering_el.findall(w("num")):
            nid = wattr(n, "numId")
            aid = child_val(n, "abstractNumId")
            if nid is None or aid is None:
                continue
            ovs: dict[int, _Override] = {}
            for o in n.findall(w("lvlOverride")):
                il = _int(wattr(o, "ilvl"), 0) or 0
                so = child(o, "startOverride")
                lv = child(o, "lvl")
                ovs[il] = _Override(
                    start=_int(wattr(so, "val")) if so is not None else None,
                    level=_parse_level(lv) if lv is not None else None,
                )
            self.nums[nid] = (aid, ovs)
        # numStyleLink: 번호 스타일이 가리키는 실제 abstractNum으로 대체
        if styles is not None:
            for aid, style_id in self.abstract_style_link.items():
                info = styles.get(style_id)
                if info is None or info.num_id is None:
                    continue
                target = self.nums.get(info.num_id)
                if target and target[0] != aid and target[0] in self.abstract:
                    self.abstract[aid] = self.abstract[target[0]]

    def abstract_id(self, num_id: str | None) -> str | None:
        entry = self.nums.get(num_id) if num_id is not None else None
        return entry[0] if entry else None

    def get_level(self, num_id: str, ilvl: int) -> Level | None:
        entry = self.nums.get(num_id)
        if not entry:
            return None
        aid, ovs = entry
        ov = ovs.get(ilvl)
        if ov is not None and ov.level is not None:
            return ov.level
        return self.abstract.get(aid, {}).get(ilvl)

    def level_for_style(self, num_id: str | None, style_id: str | None) -> int | None:
        """abstractNum의 lvl/pStyle이 이 스타일을 가리키면 그 수준."""
        if num_id is None or style_id is None:
            return None
        aid = self.abstract_id(num_id)
        if aid is None:
            return None
        for il, lv in self.abstract.get(aid, {}).items():
            if lv.pstyle == style_id:
                return il
        return None


class NumberingState:
    """문서 순서대로 번호를 세며 라벨을 렌더링한다(abstractNum 단위 카운터)."""

    def __init__(self, numbering: Numbering):
        self.numbering = numbering
        self.counters: dict[str, dict[int, int]] = {}
        self.started: set[str] = set()

    def next_label(self, num_id: str | None, ilvl: int | None) -> str | None:
        if not num_id or num_id == "0" or ilvl is None:
            return None
        entry = self.numbering.nums.get(num_id)
        if not entry:
            return None
        aid, ovs = entry
        lvl = self.numbering.get_level(num_id, ilvl)
        if lvl is None:
            return None
        counters = self.counters.setdefault(aid, {})
        if num_id not in self.started:
            self.started.add(num_id)
            for il, ov in ovs.items():
                if ov.start is not None:
                    counters[il] = ov.start - 1
        cur = counters.get(ilvl)
        counters[ilvl] = lvl.start if cur is None else cur + 1
        for deeper in [d for d in counters if d > ilvl]:
            dl = self.numbering.get_level(num_id, deeper)
            restart = dl.restart if dl else None
            if restart is None or (restart != 0 and ilvl < restart):
                del counters[deeper]
        if lvl.fmt == "bullet":
            return BULLET_MAP.get(lvl.text, lvl.text).strip() or None
        label = self._render(num_id, ilvl, lvl, counters)
        label = label.replace("\xa0", " ").strip()
        return label or None

    def _render(self, num_id: str, ilvl: int, lvl: Level, counters: dict[int, int]) -> str:
        def repl(m: re.Match[str]) -> str:
            n = int(m.group(1)) - 1
            lv = self.numbering.get_level(num_id, n)
            val = counters.get(n)
            if val is None:
                val = lv.start if lv else 1
            fmt = lv.fmt if lv else "decimal"
            if lvl.is_lgl and n < ilvl and fmt not in ("none",):
                fmt = "decimal"
            return format_number(val, fmt)

        return re.sub(r"%([1-9])", repl, lvl.text)
