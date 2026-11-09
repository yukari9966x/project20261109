#!/usr/bin/env python3
"""THIRD_PARTY_NOTICES.md 생성: 설치된 의존성(ksfix[web,llm] 기준)의 이름·버전·라이선스를 모은다."""

from __future__ import annotations

import argparse
import re
import sys
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXTRA_NOTES = """
## 함께 쓰지만 이 저장소에 포함하지 않는 구성요소

| 구성요소 | 라이선스 | 비고 |
|---|---|---|
| PyInstaller(Windows 실행파일 빌드) | GPL-2.0-or-later + 부트로더 예외 | 부트로더 예외에 따라 만든 실행파일은 자유롭게 배포할 수 있다. 실행파일 zip에는 PyInstaller 부트로더가 들어 있다 |
| Pyodide 0.27.2(브라우저 데모) | MPL-2.0 | 브라우저 데모가 CDN(cdn.jsdelivr.net)에서 내려받아 실행한다. 데모 페이지에는 포함하지 않는다 |
| python:3.12-slim(Docker 기반 이미지) | PSF-2.0 및 Debian 패키지 라이선스 | Docker 이미지를 만들 때 내려받는다 |
| Ollama | MIT | LLM 기능(선택)을 쓸 때 사용자가 따로 설치한다 |
| EXAONE 3.5 7.8B(LG AI연구원) | EXAONE AI Model License Agreement 1.1 - NC(비상업) | 평가·시연용. 모델 파일은 이 도구에 포함하지 않으며 사용자가 직접 받는다. 업무 활용 시 라이선스 확인 필요 |
| Gemma 3 4B(Google) | Gemma Terms of Use | 평가·시연용. 모델 파일은 포함하지 않는다 |

KS 표준 문서(KS A 0001:2023 등)는 저작권 보호 대상이므로 저장소에 넣지 않는다. 규칙 설명은 조항 번호와 요약만 쓰고,
도구 기능에 꼭 필요한 정형문(KS A 0001:2023 6.1.3·6.4.1·6.4.2·부속서 E·N)만 `src/ksfix/assets/boilerplate.yaml`에 담았다.
"""


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def license_of(dist: metadata.Distribution) -> str:
    md = dist.metadata
    expr = md.get("License-Expression")
    if expr:
        return expr
    classifiers = [
        c.split("::")[-1].strip()
        for c in md.get_all("Classifier") or []
        if c.startswith("License ::")
    ]
    lic = (md.get("License") or "").strip()
    if classifiers:
        return ", ".join(sorted(set(classifiers)))
    if lic and len(lic) < 80 and "\n" not in lic:
        return lic
    return "메타데이터 확인 필요"


def requirements(dist: metadata.Distribution, extras: set[str]) -> list[str]:
    out = []
    for req in dist.requires or []:
        name, _, marker = req.partition(";")
        m = re.search(r"extra\s*==\s*['\"]([^'\"]+)['\"]", marker)
        if m and m.group(1) not in extras:
            continue
        if not m and "extra" in marker:
            continue
        out.append(re.split(r"[\s<>=!~\[(]", name.strip(), maxsplit=1)[0])
    return out


def collect(
    root: str = "ksfix", extras: tuple[str, ...] = ("web", "llm")
) -> list[metadata.Distribution]:
    seen: dict[str, metadata.Distribution] = {}
    stack = [(root, set(extras))]
    while stack:
        name, ex = stack.pop()
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            continue
        key = norm(dist.metadata["Name"])
        if key in seen:
            continue
        seen[key] = dist
        for dep in requirements(dist, ex):
            stack.append((dep, set()))
    return [d for k, d in sorted(seen.items()) if k != "ksfix"]


def render() -> str:
    rows = [
        "| 패키지 | 버전 | 라이선스 | 용도 |",
        "|---|---|---|---|",
    ]
    core = {"python-docx", "lxml", "pyyaml", "jinja2", "markupsafe", "typing-extensions"}
    for d in collect():
        name = d.metadata["Name"]
        use = "코어" if norm(name) in core else "웹(FastAPI·uvicorn)"
        rows.append(f"| {name} | {d.version} | {license_of(d)} | {use} |")
    head = (
        "# 오픈소스 고지 (THIRD_PARTY_NOTICES)\n\n"
        '`python scripts/gen_notices.py`로 생성 · KS-Fix가 실행할 때 쓰는 패키지(`pip install ".[web,llm]"` 기준)와 라이선스.\n'
        "모두 허용형(permissive) 라이선스이며, LLM 호출은 표준 라이브러리(urllib)만 써서 추가 의존성이 없다.\n\n"
        "## 실행 의존성\n\n"
    )
    return head + "\n".join(rows) + "\n" + EXTRA_NOTES


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="오픈소스 고지 생성")
    ap.add_argument("-o", "--out", default=str(ROOT / "THIRD_PARTY_NOTICES.md"))
    args = ap.parse_args(argv)
    Path(args.out).write_text(render(), encoding="utf-8")
    print(f"생성: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
