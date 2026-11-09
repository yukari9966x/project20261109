"""전송 계층: CPython은 urllib(추가 의존성 없음). 브라우저(Pyodide)용 전송은 로드맵(P2).

LLM 서버 주소는 설정에서 오므로 http·https만 허용한다. urlopen 기본 처리기에는 file://·ftp:// 등도
들어 있어, 주소가 조작되면 로컬 파일을 읽을 수 있다. 그래서 스킴을 먼저 검사하고, http·https 처리기만
넣은 전용 opener로 연다(리다이렉트도 따르지 않는다).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from ksfix.llm.base import LLMConnectionError, LLMError, LLMHTTPError, LLMTimeoutError

ALLOWED_SCHEMES = ("http", "https")


def _http_only_opener() -> urllib.request.OpenerDirector:
    """http·https만 여는 opener(파일·FTP·data 처리기와 리다이렉트 처리기를 넣지 않음)."""
    opener = urllib.request.OpenerDirector()
    for handler in (
        urllib.request.ProxyHandler(),  # 환경변수 HTTPS_PROXY 등은 그대로 따른다
        urllib.request.HTTPHandler(),
        urllib.request.HTTPSHandler(),  # 기본 SSL 문맥(인증서 검증)
        urllib.request.HTTPDefaultErrorHandler(),
        urllib.request.HTTPErrorProcessor(),
        urllib.request.UnknownHandler(),  # 그 밖의 스킴은 URLError('unknown url type')
    ):
        opener.add_handler(handler)
    return opener


def check_url(url: str) -> str:
    """LLM 서버 주소 검사: http·https와 호스트가 있어야 한다."""
    parts = urllib.parse.urlsplit(url or "")
    if parts.scheme.lower() not in ALLOWED_SCHEMES or not parts.netloc:
        raise LLMError(f"LLM 서버 주소는 http:// 또는 https://로 시작해야 합니다: {url!r}")
    return url


def post_json(url: str, payload: dict, headers: dict | None = None, timeout: float = 60.0) -> Any:
    check_url(url)
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    try:
        with _http_only_opener().open(req, timeout=timeout) as resp:
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
