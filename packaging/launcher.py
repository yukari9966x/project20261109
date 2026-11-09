"""KS-Fix 실행파일 진입점: 빈 포트로 로컬 웹 서버를 띄우고 브라우저를 연다.

- 더블클릭: 웹 UI(http://127.0.0.1:<포트>) 자동 열림, 창을 닫거나 Ctrl+C로 종료
- ksfix.exe --selftest: 묶인 합성 샘플로 점검·교정·리포트가 되는지 확인(배포 전 자동 검사)
- ksfix.exe fix 파일.docx -o out: 명령줄(CLI)로도 쓸 수 있다
"""

from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path


def base_dir() -> Path:
    frozen = getattr(sys, "_MEIPASS", None)
    return Path(frozen) if frozen else Path(__file__).resolve().parent.parent


def free_port(preferred: int = 8765) -> int:
    for port in (preferred, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
            except OSError:
                continue
            return s.getsockname()[1]
    raise RuntimeError("사용할 수 있는 포트가 없습니다.")


def selftest() -> int:
    from ksfix.api import fix_bytes
    from ksfix.report import build_report, render_html
    from ksfix.web.app import find_static_dir

    sample = base_dir() / "samples" / "sample_01_violations.docx"
    r = fix_bytes(sample.read_bytes(), mode="tracked")
    rep = build_report(r.check, r, source_name=sample.name, input_unchanged=True)
    html = render_html(rep)
    checks = {
        "교정 문서 생성": r.output is not None,
        "출력 무결성": not r.integrity,
        "기술적 내용 불변": bool(r.invariants.get("ok")),
        "자동수정 적용": r.summary()["applied"] > 0,
        "체크리스트 53항목": len(rep["checklist"]["items"]) == 53,
        "HTML 리포트": "KS-Fix 점검 리포트" in html,
        "웹 UI 파일": find_static_dir() is not None,
    }
    for name, ok in checks.items():
        print(f"[{'통과' if ok else '실패'}] {name}")
    return 0 if all(checks.values()) else 1


def main(argv: list[str] | None = None) -> int:
    from ksfix.cli import _safe_streams

    _safe_streams()
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in (
        "check",
        "fix",
        "inspect",
        "rules",
        "eval",
        "serve",
        "--version",
        "-h",
        "--help",
    ):
        from ksfix.cli import main as cli_main

        return cli_main(argv)
    ap = argparse.ArgumentParser(prog="ksfix", description="KS-Fix 로컬 웹 UI 실행")
    ap.add_argument("--selftest", action="store_true", help="묶인 샘플로 자체 점검 후 종료")
    ap.add_argument("--port", type=int, default=8765, help="선호 포트(사용 중이면 빈 포트)")
    ap.add_argument("--no-browser", action="store_true", help="브라우저를 열지 않음")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    from ksfix.web.app import serve

    serve("127.0.0.1", free_port(args.port), open_browser=not args.no_browser)
    return 0


if __name__ == "__main__":
    sys.exit(main())
