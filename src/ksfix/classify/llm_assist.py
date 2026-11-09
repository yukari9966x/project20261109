"""LLM 구조 분류 보조(T2) — Phase 7에서 구현. 지금은 저신뢰 블록을 그대로 둔다."""

from __future__ import annotations

from ksfix.model.ir import KSDoc


def assist(doc: KSDoc, llm: object | None = None) -> int:
    """신뢰도 0.6 미만 블록을 LLM으로 재판정한다. 반환: 재판정한 블록 수."""
    return 0
