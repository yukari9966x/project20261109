"""OpenAI 호환 /chat/completions 어댑터(Ollama·vLLM·LM Studio·공통기반·Solar 등)."""

from __future__ import annotations

import time

from ksfix.llm.base import LLMError, LLMHTTPError, extract_json, validate
from ksfix.llm.cache import LLMCache, cache_key
from ksfix.llm.transport import post_json


class OpenAICompatClient:
    def __init__(
        self,
        name: str,
        base_url: str,
        model: str,
        *,
        api_key: str | None = None,
        external: bool = False,
        timeout: float = 180.0,
        cache: LLMCache | None = None,
        json_mode: bool = True,
        prompt_version: str = "",
    ):
        if not base_url:
            raise ValueError(f"프로필 '{name}'에 base_url이 없습니다.")
        if not model:
            raise ValueError(f"프로필 '{name}'에 model이 없습니다.")
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.external = external
        self.timeout = timeout
        self.cache = cache
        self.json_mode = json_mode
        self.prompt_version = prompt_version
        self.calls = 0
        self.cache_hits = 0
        self.last_latency = 0.0

    def complete_json(
        self,
        system: str,
        user: str,
        schema: dict,
        *,
        temperature: float = 0.0,
        timeout: float | None = None,
        prompt_version: str | None = None,
    ) -> dict:
        key = cache_key(
            self.model, prompt_version or self.prompt_version, system, user, temperature
        )
        if self.cache is not None:
            hit = self.cache.get(key)
            if hit is not None:
                self.cache_hits += 1
                self.last_latency = 0.0
                return hit
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
            "stream": False,
        }
        if self.json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        last_err = "알 수 없는 오류"
        for _attempt in range(2):  # 스키마 검증 실패 시 1회 재시도
            t0 = time.perf_counter()
            try:
                resp = post_json(
                    f"{self.base_url}/chat/completions", payload, headers, timeout or self.timeout
                )
            except LLMHTTPError as exc:
                if exc.status == 400 and "response_format" in payload:
                    payload.pop("response_format")  # JSON 모드를 모르는 서버
                    continue
                raise
            self.calls += 1
            self.last_latency = time.perf_counter() - t0
            try:
                content = resp["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError):
                last_err = "응답 형식이 OpenAI 호환이 아닙니다."
                continue
            obj = extract_json(content or "")
            if obj is not None and validate(obj, schema):
                if self.cache is not None:
                    self.cache.put(key, obj)
                return obj
            last_err = "응답 JSON이 스키마와 맞지 않습니다."
        raise LLMError(last_err)
