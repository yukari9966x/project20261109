"""패키지에 포함된 데이터 파일(정형문·KSDT 프로필) 로더."""

from __future__ import annotations

from functools import cache
from importlib import resources
from typing import Any

import yaml


def read_text(name: str) -> str:
    return resources.files(__name__).joinpath(name).read_text(encoding="utf-8")


@cache
def load_yaml(name: str) -> Any:
    return yaml.safe_load(read_text(name))


def boilerplate() -> dict:
    return load_yaml("boilerplate.yaml")
