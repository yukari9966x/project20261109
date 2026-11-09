from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples"
LOCAL = ROOT / "local_samples"
SAMPLE_NAMES = ("sample_01_violations", "sample_02_clean", "sample_03_messy_styles")


def load_make_samples():
    spec = importlib.util.spec_from_file_location(
        "make_samples", ROOT / "scripts" / "make_samples.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["make_samples"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def samples_dir() -> Path:
    if not all((SAMPLES / f"{n}.docx").exists() for n in SAMPLE_NAMES):
        load_make_samples().write_all(SAMPLES)
    return SAMPLES


@pytest.fixture(scope="session")
def sample_bytes(samples_dir) -> dict[str, bytes]:
    return {n: (samples_dir / f"{n}.docx").read_bytes() for n in SAMPLE_NAMES}


def local_docs() -> list[Path]:
    if not LOCAL.is_dir():
        return []
    return sorted(p for p in LOCAL.glob("*.docx") if not p.name.startswith("~$"))


@pytest.fixture(scope="session")
def real_docs() -> list[Path]:
    docs = local_docs()
    if not docs:
        pytest.skip("local_samples/에 실제 KS 문서가 없어 건너뜀")
    return docs
