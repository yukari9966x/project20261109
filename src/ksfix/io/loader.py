"""docx bytes → python-docx Document (입력 bytes는 절대 수정하지 않는다)."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from ksfix.io.safety import DEFAULT_MAX_BYTES, InputError, validate_docx


def read_input(path: str | Path) -> bytes:
    """입력 파일을 읽기 전용으로 연다."""
    p = Path(path)
    if not p.is_file():
        raise InputError(f"파일을 찾을 수 없습니다: {p}")
    with p.open("rb") as fh:
        return fh.read()


def open_docx(data: bytes, max_bytes: int = DEFAULT_MAX_BYTES) -> tuple[Any, str]:
    """검증 후 python-docx Document와 SHA-256을 돌려준다."""
    digest = validate_docx(data, max_bytes=max_bytes)
    try:
        import docx  # python-docx

        document = docx.Document(io.BytesIO(bytes(data)))
    except InputError:
        raise
    except Exception as exc:
        raise InputError(f"문서를 열 수 없습니다: {type(exc).__name__}: {exc}") from exc
    return document, digest
