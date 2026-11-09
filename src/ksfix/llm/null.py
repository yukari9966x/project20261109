"""LLM 끔(기본값). 핵심 기능은 LLM 없이 동작한다."""

from __future__ import annotations

from ksfix.llm.base import LLMError


class NullLLM:
    name = "none"
    model = ""
    external = False

    def complete_json(self, system: str, user: str, schema: dict, **_: object) -> dict:
        raise LLMError("LLM이 꺼져 있습니다.")
