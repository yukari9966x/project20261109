"""패키지에 포함된 데이터 파일(정형문·KSDT 프로필) 로더."""

from __future__ import annotations

from functools import cache
from typing import Any

import yaml

from ksfix._paths import read_pkg_text


def read_text(name: str) -> str:
    return read_pkg_text("assets", name)


@cache
def load_yaml(name: str) -> Any:
    return yaml.safe_load(read_text(name))


def boilerplate() -> dict:
    return load_yaml("boilerplate.yaml")
