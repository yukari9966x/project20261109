"""T2 구조 분류 보조: 신뢰도 0.6 미만 블록을 묶음(최대 20, 앞뒤 문맥 포함)으로 재판정."""

from __future__ import annotations

import json
from functools import cache

from ksfix._paths import read_pkg_text
from ksfix.llm.base import LLMError
from ksfix.model.ir import KSDoc, Role

PROMPT_VERSION = "classify_blocks.v1"
SCHEMA = {"required": ["items"], "list": "items", "item_required": ["id", "role"]}
MIN_CONF = 0.6
ALLOWED = {
    "heading", "body", "list_item", "note", "example", "remark", "table_caption", "figure_caption",
    "unit_label", "formula", "normref_entry", "biblio_entry", "term", "definition", "term_source",
    "foreword", "intro", "commentary", "cover", "back_cover",
}  # fmt: skip


@cache
def load_prompt() -> tuple[str, str]:
    text = read_pkg_text("llm", "prompts", "classify_blocks.v1.md")
    sys_part, user_part = text.split("[사용자]", 1)
    return sys_part.replace("[시스템]", "", 1).strip(), user_part.strip()


def assist(doc: KSDoc, llm, batch_size: int = 20) -> int:
    """반환: 역할을 바꾼 블록 수."""
    targets = [
        p for p in doc.paras if p.role != Role.EMPTY and not p.in_table and p.role_conf < MIN_CONF
    ]
    if llm is None or not targets:
        return 0
    system, tmpl = load_prompt()
    changed = 0
    paras = doc.paras
    for i in range(0, len(targets), batch_size):
        batch = targets[i : i + batch_size]
        items = []
        for p in batch:
            prev = next((q.text for q in reversed(paras[: p.idx]) if q.text.strip()), "")
            nxt = next((q.text for q in paras[p.idx + 1 :] if q.text.strip()), "")
            items.append(
                {
                    "id": str(p.idx),
                    "text": p.text[:300],
                    "앞": prev[:120],
                    "뒤": nxt[:120],
                    "스타일": p.style_name,
                }
            )
        user = tmpl.replace("{items_json}", json.dumps(items, ensure_ascii=False))
        try:
            resp = llm.complete_json(
                system, user, SCHEMA, temperature=0.0, prompt_version=PROMPT_VERSION
            )
        except LLMError:
            continue
        for x in resp.get("items", []):
            try:
                idx = int(x.get("id"))
                conf = float(x.get("confidence", 0))
            except (TypeError, ValueError):
                continue
            role = x.get("role")
            if role in ALLOWED and conf >= MIN_CONF and 0 <= idx < len(paras):
                p = paras[idx]
                p.role = Role(role)
                p.role_conf = conf
                p.attrs["role_source"] = "llm"
                changed += 1
    return changed
