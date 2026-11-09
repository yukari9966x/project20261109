"""전송 계층: CPython은 urllib(추가 의존성 없음). 브라우저(Pyodide)용 전송은 로드맵(P2)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from ksfix.llm.base import LLMConnectionError, LLMError, LLMHTTPError, LLMTimeoutError


def post_json(url: str, payload: dict, headers: dict | None = None, timeout: float = 60.0) -> Any:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
    except urllib.error.HTTPError as exc:
        raise LLMHTTPError(exc.code, exc.read().decode("utf-8", "replace")) from exc
    except TimeoutError as exc:  # 연결 뒤 응답 대기·읽기 중 시간 초과(urllib이 감싸지 않음)
        raise LLMTimeoutError(f"응답 시간 초과({timeout:.0f}초)") from exc
    except urllib.error.URLError as exc:  # 연결 단계 오류(연결 시간 초과 포함)
        if isinstance(exc.reason, TimeoutError):
            raise LLMConnectionError(f"연결 시간 초과({timeout:.0f}초)") from exc
        raise LLMConnectionError(f"연결 실패: {exc.reason}") from exc
    except (ConnectionError, OSError) as exc:
        raise LLMConnectionError(f"연결 실패: {exc}") from exc
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LLMError("응답이 JSON이 아닙니다.") from exc
