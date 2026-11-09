"""패키지 데이터 파일 경로(소스·휠 설치·PyInstaller·Pyodide 모두 같은 방식으로 찾는다)."""

from __future__ import annotations

from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent


def pkg_path(*parts: str) -> Path:
    return PKG_DIR.joinpath(*parts)


def read_pkg_text(*parts: str) -> str:
    return pkg_path(*parts).read_text(encoding="utf-8")
