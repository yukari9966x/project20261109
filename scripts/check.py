#!/usr/bin/env python3
"""로컬·GitHub Actions·GitLab CI 공통 품질 검사.

단계: ruff lint → ruff format 검사 → 저장소 위생(실제 KS 문서·비밀값) → pytest → 샘플 1 처리.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "samples" / "sample_01_violations.docx"

STEPS: list[list[str]] = [
    [sys.executable, "-m", "ruff", "check", "src", "tests", "scripts"],
    [sys.executable, "-m", "ruff", "format", "--check", "src", "tests", "scripts"],
    [sys.executable, "-m", "pytest", "-q"],
]

SAMPLE_STEP = [
    sys.executable,
    "-m",
    "ksfix",
    "fix",
    str(SAMPLE.relative_to(ROOT)),
    "-o",
    "out/ci",
    "--mode",
    "tracked",
]

# 값이 붙은 비밀값 할당만 잡는다(예: api_key = "sk-..."). 환경변수 이름 참조는 허용.
SECRET_RE = re.compile(
    r"""(?i)(api[_-]?key|secret|password|passwd|token)\s*[:=]\s*["']([^"'\s$<{]{12,})["']"""
)
SECRET_ALLOW = ("example", "dummy", "placeholder", "xxxx", "changeme")


def _git_ls_files() -> list[str] | None:
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return [line for line in out.splitlines() if line]


def hygiene() -> bool:
    """실제 KS 문서·비밀값이 저장소에 들어가지 않았는지 확인한다."""
    files = _git_ls_files()
    if files is None:
        print("  (git 정보를 읽을 수 없어 저장소 위생 검사를 건너뜀)")
        return True
    ok = True
    leaked = [f for f in files if f.startswith("local_samples/")]
    if leaked:
        print("  ✗ local_samples/ 파일이 추적되고 있습니다:", leaked[:5])
        ok = False
    for name in files:
        path = ROOT / name
        if path.suffix.lower() not in {
            ".py",
            ".yaml",
            ".yml",
            ".toml",
            ".md",
            ".json",
            ".txt",
            ".js",
            ".env",
            ".sh",
            ".cfg",
            ".ini",
        } and not name.endswith(".env.example"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for m in SECRET_RE.finditer(text):
            if any(a in m.group(2).lower() for a in SECRET_ALLOW):
                continue
            print(f"  ✗ 비밀값으로 보이는 문자열: {name}: {m.group(1)}=…")
            ok = False
    if ok:
        print("  저장소 위생 검사 통과(local_samples 미추적, 비밀값 패턴 없음)")
    return ok


def run(step: list[str]) -> bool:
    print("$", " ".join(step), flush=True)
    return subprocess.run(step, cwd=ROOT).returncode == 0


def main() -> int:
    for step in STEPS[:2]:
        if not run(step):
            return 1
    print("$ (저장소 위생 검사)", flush=True)
    if not hygiene():
        return 1
    if not run(STEPS[2]):
        return 1
    if SAMPLE.exists():
        if not run(SAMPLE_STEP):
            return 1
    else:
        print(
            f"  (샘플 없음: {SAMPLE.relative_to(ROOT)} — `python scripts/make_samples.py` 후 처리 검사)"
        )
    print("모든 검사 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
