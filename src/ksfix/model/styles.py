"""스타일 시트 해석: 스타일 ID는 문서마다 다르므로 이름과 상속 체인(basedOn)으로 다룬다."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ksfix.model.ns import child, child_val, on_off, w, wattr


def norm_style_name(name: str | None) -> str:
    """대소문자·공백 차이를 없앤 비교용 이름. 'Heading 1' == 'heading 1'."""
    if not name:
        return ""
    return re.sub(r"\s+", " ", name).strip().lower()


@dataclass
class StyleInfo:
    style_id: str
    name: str | None
    type: str | None
    based_on: str | None
    num_id: str | None
    ilvl: int | None
    outline_lvl: int | None
    jc: str | None
    bold: bool | None
    size_half_pt: int | None
    is_default: bool

    @property
    def norm_name(self) -> str:
        return norm_style_name(self.name)


def _int(val: str | None) -> int | None:
    try:
        return int(val) if val is not None else None
    except ValueError:
        return None


class StyleSheet:
    def __init__(self, styles_el: Any | None):
        self.el = styles_el
        self.styles: dict[str, StyleInfo] = {}
        self._by_name: dict[str, str] = {}
        self.default_para: str | None = None
        if styles_el is None:
            return
        for s in styles_el.findall(w("style")):
            sid = wattr(s, "styleId")
            if not sid:
                continue
            ppr = child(s, "pPr")
            rpr = child(s, "rPr")
            numpr = child(ppr, "numPr") if ppr is not None else None
            info = StyleInfo(
                style_id=sid,
                name=child_val(s, "name"),
                type=wattr(s, "type"),
                based_on=child_val(s, "basedOn"),
                num_id=child_val(numpr, "numId") if numpr is not None else None,
                ilvl=_int(child_val(numpr, "ilvl")) if numpr is not None else None,
                outline_lvl=_int(child_val(ppr, "outlineLvl")) if ppr is not None else None,
                jc=child_val(ppr, "jc") if ppr is not None else None,
                bold=on_off(child(rpr, "b")) if rpr is not None else None,
                size_half_pt=_int(child_val(rpr, "sz")) if rpr is not None else None,
                is_default=(wattr(s, "default") in ("1", "true")),
            )
            self.styles[sid] = info
            if info.name:
                self._by_name.setdefault(info.norm_name, sid)
            if info.type == "paragraph" and info.is_default:
                self.default_para = sid

    def get(self, sid: str | None) -> StyleInfo | None:
        if sid is None:
            return None
        return self.styles.get(sid)

    def name(self, sid: str | None) -> str | None:
        info = self.get(sid if sid is not None else self.default_para)
        return info.name if info else None

    def find_by_name(self, name: str) -> str | None:
        return self._by_name.get(norm_style_name(name))

    def chain(self, sid: str | None) -> list[StyleInfo]:
        """sid부터 basedOn을 따라 올라간 스타일 목록(순환 방지)."""
        out: list[StyleInfo] = []
        seen: set[str] = set()
        cur = sid if sid is not None else self.default_para
        while cur and cur not in seen:
            seen.add(cur)
            info = self.styles.get(cur)
            if info is None:
                break
            out.append(info)
            cur = info.based_on
        return out

    def chain_names(self, sid: str | None) -> list[str]:
        return [s.norm_name for s in self.chain(sid)]

    def resolve(self, sid: str | None, attr: str) -> Any:
        for info in self.chain(sid):
            val = getattr(info, attr)
            if val is not None:
                return val
        return None

    def resolve_numpr(self, sid: str | None) -> tuple[str | None, int | None]:
        """스타일 상속 체인에서 numId와 ilvl을 각각 가장 가까운 값으로 찾는다."""
        num_id: str | None = None
        ilvl: int | None = None
        for info in self.chain(sid):
            if num_id is None and info.num_id is not None:
                num_id = info.num_id
            if ilvl is None and info.ilvl is not None:
                ilvl = info.ilvl
        return num_id, ilvl

    def heading_level(self, sid: str | None) -> int | None:
        """'heading N' 스타일(또는 그 파생)이면 N."""
        for info in self.chain(sid):
            m = re.fullmatch(r"heading ([1-9])", info.norm_name)
            if m:
                return int(m.group(1))
        return None
