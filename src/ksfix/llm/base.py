"""LLM 클라이언트 인터페이스(모델 비종속)."""

from __future__ import annotations

import json
import re
from typing import Any, Protocol


class LLMError(RuntimeError):
    """LLM 호출 실패(연결·시간 초과·잘못된 응답)."""


class LLMConnectionError(LLMError):
    """서버에 닿지 못함(연결 거부·주소 오류·연결 시간 초과). 같은 서버에 더 묻지 않는다."""


class LLMTimeoutError(LLMError):
    """연결은 됐지만 응답이 제한 시간 안에 오지 않음(느린 CPU 추론 등). 더 짧게 다시 물을 수 있다."""


class LLMHTTPError(LLMError):
    def __init__(self, status: int, body: str):
        super().__init__(f"HTTP {status}: {body[:200]}")
        self.status = status
        self.body = body


class LLMClient(Protocol):
    name: str  # 예: "ollama/exaone3.5:7.8b"
    model: str
    external: bool  # True면 문서 문장이 외부로 전송된다

    def complete_json(
        self,
        system: str,
        user: str,
        schema: dict,
        *,
        temperature: float = 0.0,
        timeout: float = 60.0,
    ) -> dict: ...


FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def extract_json(text: str) -> Any:
    """응답에서 첫 JSON 객체를 꺼낸다(코드 펜스·앞뒤 설명 허용)."""
    if not text:
        return None
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = FENCE_RE.search(text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    start = text.find("{")
    while start >= 0:
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    return None


def validate(obj: Any, schema: dict) -> bool:
    """가벼운 스키마 검사: {"required": [...], "list": "items", "item_required": [...]}."""
    if not schema:
        return isinstance(obj, dict | list)
    if not isinstance(obj, dict):
        return False
    for key in schema.get("required", []):
        if key not in obj:
            return False
    lst = schema.get("list")
    if lst:
        items = obj.get(lst)
        if not isinstance(items, list):
            return False
        for it in items:
            if not isinstance(it, dict):
                return False
            for key in schema.get("item_required", []):
                if key not in it:
                    return False
    return True
