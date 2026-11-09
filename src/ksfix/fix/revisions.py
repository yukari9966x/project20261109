"""변경추적 ID 발급·작성자·일시. ID는 문서 안 기존 최댓값 + 1000부터 발급한다."""

from __future__ import annotations

import datetime as dt
from typing import Any

from docx.opc.part import XmlPart

from ksfix.model.ns import w

AUTHOR = "KS-Fix"
INITIALS = "KF"


def max_w_id(document: Any) -> int:
    best = 0
    attr = w("id")
    for part in document.part.package.iter_parts():
        if not isinstance(part, XmlPart):
            continue
        for el in part.element.iter():
            val = el.get(attr) if isinstance(el.tag, str) else None
            if val is not None and val.lstrip("-").isdigit():
                best = max(best, int(val))
    return best


def iso_now() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


class Revisions:
    def __init__(self, document: Any, author: str = AUTHOR, date: str | None = None):
        self.author = author
        self.date = date or iso_now()
        self._next = max_w_id(document) + 1000

    def new_id(self) -> int:
        nid = self._next
        self._next += 1
        return nid

    def attrs(self) -> dict[str, str]:
        return {w("id"): str(self.new_id()), w("author"): self.author, w("date"): self.date}
