"""KS-Fix 명령줄 인터페이스(argparse)."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence

from ksfix import __version__

DESCRIPTION = "KS-Fix — KS A 0001:2023에 맞춰 표준안(docx)을 점검·교정합니다."


def _not_ready(phase: str) -> Callable[[argparse.Namespace], int]:
    def handler(args: argparse.Namespace) -> int:
        print(f"'{args.command}' 명령은 아직 구현되지 않았습니다({phase}).", file=sys.stderr)
        return 2

    return handler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ksfix", description=DESCRIPTION)
    parser.add_argument("--version", action="version", version=f"ksfix {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="명령")

    p = sub.add_parser("check", help="점검만 하고 JSON·HTML 리포트를 만든다")
    p.add_argument("file", help="입력 docx")
    p.add_argument("-o", "--out", default="out", help="출력 디렉터리(기본: out)")
    p.add_argument("--rules", default=None, help="규칙 우선순위 범위(예: P0,P0b) 또는 규칙 ID 목록")
    p.add_argument("--llm", default=None, help="LLM 프로필 이름(기본: none)")
    p.add_argument(
        "--fail-on",
        choices=["error", "warning", "info", "never"],
        default="never",
        help="이 심각도 이상의 지적이 있으면 종료 코드 1",
    )
    p.set_defaults(func=_not_ready("Phase 3"))

    p = sub.add_parser("fix", help="점검 + 교정 문서(변경추적/반영본) + 리포트")
    p.add_argument("file", help="입력 docx")
    p.add_argument("-o", "--out", default="out", help="출력 디렉터리(기본: out)")
    p.add_argument("--mode", choices=["tracked", "clean", "report"], default="tracked")
    p.add_argument("--rules", default=None, help="규칙 우선순위 범위(예: P0,P0b) 또는 규칙 ID 목록")
    p.add_argument("--llm", default=None, help="LLM 프로필 이름(기본: none)")
    p.add_argument(
        "--accept-existing-changes",
        action="store_true",
        help="기존 변경추적이 있는 문서도 자동 수정한다(기본: 메모만)",
    )
    p.set_defaults(func=_not_ready("Phase 4"))

    p = sub.add_parser("inspect", help="블록별 역할·번호·스타일 보기(디버깅·시연용)")
    p.add_argument("file", help="입력 docx")
    p.add_argument("--json", action="store_true", help="JSON으로 출력")
    p.set_defaults(func=_not_ready("Phase 1"))

    p = sub.add_parser("rules", help="규칙 목록")
    p.add_argument("--markdown", action="store_true", help="마크다운 표로 출력(docs/RULES.md)")
    p.set_defaults(func=_not_ready("Phase 3"))

    p = sub.add_parser("eval", help="LLM 골드셋 평가(모델 비종속 입증)")
    p.add_argument("--profiles", required=True, help="쉼표로 구분한 프로필 이름")
    p.set_defaults(func=_not_ready("Phase 7"))

    p = sub.add_parser("serve", help="로컬 웹 UI")
    p.add_argument("--host", default=None, help="바인딩 주소(기본: 127.0.0.1)")
    p.add_argument("--port", type=int, default=None, help="포트(기본: 8765)")
    p.add_argument("--open", action="store_true", help="브라우저를 자동으로 연다")
    p.set_defaults(func=_not_ready("Phase 6"))

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    return int(args.func(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
