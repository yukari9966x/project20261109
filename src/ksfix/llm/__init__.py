"""LLM 보조 계층(선택): 모델 비종속 OpenAI 호환 어댑터 + 좁고 검증 가능한 작업(T1·T2)."""

from ksfix.llm.base import LLMClient, LLMError

__all__ = ["LLMClient", "LLMError"]
