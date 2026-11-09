#!/usr/bin/env python3
"""examples/ 생성: 합성 샘플을 처리한 결과물(변경추적본·반영본·리포트·감사 로그).

설치하기 전에도 결과를 볼 수 있게 저장소에 함께 둔다. 규칙이나 수정 엔진을 바꾸면 다시 만든다
(tests/golden/test_examples.py가 어긋남을 알려 준다). LLM은 쓰지 않는다(--llm none).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ksfix.api import check_bytes, fix_bytes
from ksfix.cli import OUT_SUFFIX, write_reports
from ksfix.report import build_report
from make_samples import deterministic_zip

ROOT = Path(__file__).resolve().parent.parent
DATE = "2026-11-11T00:00:00Z"  # 변경추적 날짜·리포트 생성 시각 고정(다시 만들어도 같은 내용)


def _report(check, fix, name: str) -> dict:
    report = build_report(check, fix, source_name=name, input_unchanged=True if fix else None)
    report["generated_at"] = DATE
    return report


def make(out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    src = ROOT / "samples" / "sample_01_violations.docx"
    data = src.read_bytes()
    for mode in ("tracked", "clean"):
        result = fix_bytes(data, mode=mode, date=DATE)
        if not (result.invariants.get("ok") and not result.integrity):
            raise SystemExit(f"{mode}: 불변성·무결성 검사 실패 — 예시를 만들지 않습니다.")
        target = out / f"{src.stem}{OUT_SUFFIX[mode]}"
        target.write_bytes(deterministic_zip(result.output))
        written.append(target)
        if mode == "tracked":
            audit = out / f"{src.stem}.ksfix-audit.jsonl"
            audit.write_text(
                "".join(
                    json.dumps({**row, "time": DATE}, ensure_ascii=False) + "\n"
                    for row in result.audit
                ),
                encoding="utf-8",
            )
            written.append(audit)
            written += write_reports(_report(result.check, result, src.name), out, src.stem)
    clean = ROOT / "samples" / "sample_02_clean.docx"
    check = check_bytes(clean.read_bytes())
    written += write_reports(_report(check, None, clean.name), out, clean.stem)
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="예시 결과물(examples/) 생성")
    ap.add_argument("-o", "--out", default=str(ROOT / "examples"))
    args = ap.parse_args(argv)
    for path in make(Path(args.out)):
        print(f"생성: {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
