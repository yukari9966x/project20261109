"""word/settings.xml: Word가 열 때 목차 등 필드를 갱신하게 한다(<w:updateFields w:val="true"/>)."""

from __future__ import annotations

from typing import Any

from docx.opc.constants import RELATIONSHIP_TYPE as RT
from lxml import etree

from ksfix.model.builder import part_by_reltype
from ksfix.model.ns import w

# 스키마상 updateFields 뒤에 오는 요소들(이 중 처음 나오는 것 앞에 넣는다)
AFTER_UPDATE_FIELDS = [
    "hdrShapeDefaults", "footnotePr", "endnotePr", "compat", "docVars", "rsids", "mathPr",
    "attachedSchema", "themeFontLang", "clrSchemeMapping", "doNotIncludeSubdocsInStats",
    "doNotAutoCompressPictures", "forceUpgrade", "captions", "readModeInkLockDown", "smartTagType",
    "schemaLibrary", "shapeDefaults", "doNotEmbedSmartTags", "decimalSymbol", "listSeparator",
]  # fmt: skip


def set_update_fields(document: Any) -> bool:
    part = part_by_reltype(document.part, RT.SETTINGS)
    if part is None:
        return False
    settings = part.element
    el = settings.find(w("updateFields"))
    if el is None:
        el = etree.Element(w("updateFields"))
        for name in AFTER_UPDATE_FIELDS:
            anchor = settings.find(w(name))
            if anchor is not None:
                anchor.addprevious(el)
                break
        else:
            settings.append(el)
    el.set(w("val"), "true")
    return True
