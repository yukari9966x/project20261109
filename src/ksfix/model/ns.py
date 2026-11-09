"""OOXML 네임스페이스와 작은 XML 도우미."""

from __future__ import annotations

from typing import Any

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
XML_NS = "http://www.w3.org/XML/1998/namespace"

NSMAP = {"w": W_NS, "m": M_NS, "mc": MC_NS, "r": R_NS}


def w(tag: str) -> str:
    """'p' → '{w-namespace}p'."""
    return f"{{{W_NS}}}{tag}"


def wattr(el: Any, name: str) -> str | None:
    if el is None:
        return None
    return el.get(w(name))


def local(tag: Any) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def ns_of(tag: Any) -> str:
    if not isinstance(tag, str) or not tag.startswith("{"):
        return ""
    return tag[1:].split("}", 1)[0]


def is_w(el: Any, name: str) -> bool:
    return isinstance(el.tag, str) and el.tag == w(name)


def child(el: Any, name: str) -> Any:
    if el is None:
        return None
    return el.find(w(name))


def child_val(el: Any, name: str) -> str | None:
    c = child(el, name)
    return wattr(c, "val") if c is not None else None


def on_off(el: Any) -> bool | None:
    """w:b·w:i 같은 on/off 속성 요소 해석. 없으면 None."""
    if el is None:
        return None
    val = wattr(el, "val")
    if val is None:
        return True
    return val.lower() not in ("0", "false", "off", "none")
