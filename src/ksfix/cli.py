"""KS-Fix 명령줄 인터페이스(argparse)."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Sequence

from ksfix import __version__

DESCRIPTION = "KS-Fix — KS A 0001:2023에 맞춰 표준안(docx)을 점검·교정합니다."


def _not_ready(phase: str) -> Callable[[argparse.Namespace], int]:
    def handler(args: argparse.Namespace) -> int:
        print(f"'{args.command}' 명령은 아직 구현되지 않았습니다({phase}).", file=sys.stderr)
        return 2

    return handler


def _short(text: str, width: int = 60) -> str:
    text = text.replace("\n", "⏎").replace("\t", "→")
    return text if len(text) <= width else text[: width - 1] + "…"


def cmd_inspect(args: argparse.Namespace) -> int:
    import json

    from ksfix.api import inspect_bytes
    from ksfix.io import InputError, read_input

    try:
        result = inspect_bytes(read_input(args.file))
    except InputError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
        return 0
    meta = result["meta"]
    print(
        f"문단 {meta['paragraph_count']}개 · 표 {meta['table_count']}개 · 구역 {meta['sections']}개 · "
        f"한글 비율 {meta['hangul_ratio']:.0%} · 메모 {meta['comment_count']}건"
        + (" · 기존 변경추적 있음" if meta["has_tracked_changes"] else "")
    )
    print(f"{'idx':>5} {'구역':>2} {'역할':16} {'번호':10} {'스타일':24} 텍스트")
    for b in result["blocks"]:
        if not args.all and (b["in_table"] or not b["text"].strip()) and not b["label"]:
            continue
        print(
            f"{b['idx']:>5} {b['section']:>2} {b['role']:16} {str(b['label'] or ''):10} "
            f"{str(b['style'] or '')[:24]:24} {_short(b['text'])}"
        )
    return 0


SEV_KO = {"error": "오류", "warning": "경고", "info": "참고"}
FAIL_LEVEL = {"error": 0, "warning": 1, "info": 2, "never": -1}


def _print_summary(result, name: str, limit: int = 30) -> None:
    from collections import Counter

    s = result.summary()
    c = s["by_severity"]
    print(f"KS-Fix 점검: {name}")
    for w in result.warnings:
        print(f"  ! {w}")
    print(
        f"  지적 {s['findings']}건 (오류 {c['error']} · 경고 {c['warning']} · 참고 {c['info']}) · "
        f"자동수정 가능 {s['autofixable']}건 · 규칙 통과율 {s['pass_rate']}% "
        f"({s['rules_passed']}/{s['rules_applied']})"
    )
    by_rule = Counter(f.rule_id for f in result.findings)
    if by_rule:
        print("  규칙별: " + ", ".join(f"{k} {v}" for k, v in sorted(by_rule.items())))
    for f in result.findings[:limit]:
        print(
            f"  [{SEV_KO[f.severity]}] {f.rule_id} #{f.block}: {f.message} «{_short(f.snippet, 50)}»"
        )
    if len(result.findings) > limit:
        print(f"  … 외 {len(result.findings) - limit}건(리포트 참고)")
    for d in result.diagnostics:
        print(f"  ! 내부 오류({d.get('failed_rule')}): {d.get('error')}")


def _exit_code(result, fail_on: str) -> int:
    level = FAIL_LEVEL.get(fail_on, -1)
    if level < 0:
        return 0
    worst = min((FAIL_LEVEL[f.severity] for f in result.findings), default=99)
    return 1 if worst <= level else 0


def _llm_client(name: str | None):
    """--llm 값 → 클라이언트(끔이면 None). 외부 API면 경고를 찍는다."""
    from ksfix.llm.config import make_client

    client = make_client(name) if name else make_client(None)
    if client is not None:
        where = "외부" if client.external else "로컬"
        print(f"  LLM: {client.name} ({where})", file=sys.stderr)
        if client.external:
            print("  ⚠ 외부 API 프로필입니다. 문서 문장이 외부로 전송됩니다.", file=sys.stderr)
    return client


def cmd_check(args: argparse.Namespace) -> int:
    from pathlib import Path

    from ksfix.api import check_bytes
    from ksfix.io import InputError, read_input
    from ksfix.report import build_report

    try:
        data = read_input(args.file)
        result = check_bytes(data, rules=args.rules, llm=_llm_client(args.llm))
    except (InputError, ValueError, KeyError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 2
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    src = Path(args.file)
    report = build_report(result, None, source_name=src.name)
    paths = write_reports(report, out, src.stem)
    _print_summary(result, src.name)
    for path in paths:
        print(f"  리포트: {path}")
    return _exit_code(result, args.fail_on)


def write_reports(report: dict, out, stem: str) -> list:
    import json

    from ksfix.report import render_html

    jpath = out / f"{stem}.ksfix-report.json"
    jpath.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    hpath = out / f"{stem}.ksfix-report.html"
    hpath.write_text(render_html(report), encoding="utf-8")
    return [hpath, jpath]


OUT_SUFFIX = {"tracked": ".ksfix-tracked.docx", "clean": ".ksfix-clean.docx"}


def cmd_fix(args: argparse.Namespace) -> int:
    import json
    from pathlib import Path

    from ksfix.api import fix_bytes
    from ksfix.io import InputError, read_input, sha256
    from ksfix.report import build_report

    src = Path(args.file)
    try:
        data = read_input(src)
        before_hash = sha256(data)
        result = fix_bytes(
            data,
            mode=args.mode,
            rules=args.rules,
            llm=_llm_client(args.llm),
            accept_existing_changes=args.accept_existing_changes,
        )
    except (InputError, ValueError, KeyError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 2
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    if result.output is not None:
        target = out / f"{src.stem}{OUT_SUFFIX[args.mode]}"
        if target.resolve() == src.resolve():
            print("오류: 출력 파일이 입력 파일과 같습니다.", file=sys.stderr)
            return 2
        target.write_bytes(result.output)
        written.append(target)
    audit_path = out / f"{src.stem}.ksfix-audit.jsonl"
    with audit_path.open("w", encoding="utf-8") as fh:
        for row in result.audit:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    written.append(audit_path)
    input_ok = sha256(read_input(src)) == before_hash
    report = build_report(result.check, result, source_name=src.name, input_unchanged=input_ok)
    written = write_reports(report, out, src.stem) + written
    _print_summary(result.check, src.name, limit=10)
    s = result.summary()
    print(
        f"  교정({args.mode}): 자동수정 {s['applied']}건 · 제안 {s['suggested']}건 · 메모 {s['comments']}건 · "
        f"규칙 통과율 {s['pass_rate_before']}% → {s['pass_rate_after']}%"
    )
    print(
        f"  검증: 기술적 내용 불변 {'통과' if s['invariants_ok'] else '실패(편집 철회)'} · "
        f"출력 무결성 {'통과' if s['integrity_ok'] else '실패: ' + '; '.join(result.integrity)} · "
        f"입력 파일 불변 {'통과' if input_ok else '실패'}"
    )
    for path in written:
        print(f"  출력: {path}")
    if not input_ok or result.integrity:
        return 3
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    from pathlib import Path

    from ksfix.llm.eval import run_eval

    gold = args.gold or str(
        Path(__file__).resolve().parents[2] / "tests" / "llm_gold" / "modal_verbs.jsonl"
    )
    if not Path(gold).is_file():
        print(f"골드셋을 찾을 수 없습니다: {gold} (--gold로 지정)", file=sys.stderr)
        return 2
    names = [p.strip() for p in args.profiles.split(",") if p.strip()]
    try:
        results = run_eval(names, gold, args.out, use_cache=args.cache)
    except (KeyError, ValueError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 2
    for r in results:
        comp = "-" if r["compliance_accuracy"] is None else f"{100 * r['compliance_accuracy']:.0f}%"
        print(
            f"{r['profile']:16} {r['model']:22} 유형 정확도 {100 * r['accuracy']:.0f}% · "
            f"허용 판별 {100 * r['permission_accuracy']:.0f}% · 적합성 {comp} · "
            f"판단보류 {r['held']} · 문장당 {r['sec_per_sentence']}초"
        )
    print(f"평가표: {Path(args.out) / 'modal_verbs_eval.md'}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    try:
        from ksfix.web.app import serve
    except ImportError:
        print('웹 기능이 설치되어 있지 않습니다: pip install -e ".[web]"', file=sys.stderr)
        return 2
    serve(args.host, args.port, args.open)
    return 0


def cmd_rules(args: argparse.Namespace) -> int:
    from ksfix.rules.registry import implemented_ids, load_catalog

    cat = load_catalog()
    impl = implemented_ids()
    if args.markdown:
        print(rules_markdown(cat, impl))
        return 0
    print(
        f"{cat.title} — 규칙 {len(cat.rules)}종, 구현 {sum(r['id'] in impl for r in cat.rules)}종"
    )
    for r in cat.rules:
        mark = "●" if r["id"] in impl else "○"
        print(
            f" {mark} {r['id']:7} {r['priority']:3} {SEV_KO[r['severity']]:2} {r['autofix']:7} {r['title']}"
        )
    return 0


def rules_markdown(cat, impl: set[str]) -> str:
    autofix_ko = {"auto": "자동", "suggest": "제안", "none": "메모"}
    method_ko = {"deterministic": "결정", "llm": "LLM", "hybrid": "결정+LLM"}
    lines = [
        "# 규칙 목록 (RULES)",
        "",
        f"`ksfix rules --markdown`으로 생성 · 규칙팩 {cat.pack} {cat.version} · "
        f"전체 {len(cat.rules)}종 중 구현 {sum(r['id'] in impl for r in cat.rules)}종",
        "",
        "근거는 KS A 0001:2023의 절·부속서 번호입니다(요약 서술). "
        "수정: 자동 = 변경추적 자동 수정 / 제안 = 메모·제안 / 메모 = 지적만.",
        "",
    ]
    by_cat: dict[str, list[dict]] = {}
    for r in cat.rules:
        by_cat.setdefault(r["category"], []).append(r)
    for name, rules in by_cat.items():
        lines += [
            f"## {name}",
            "",
            "| ID | 구현 | 우선 | 심각도 | 방식 | 수정 | 점검 내용 | 근거 |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for r in rules:
            lines.append(
                f"| {r['id']} | {'●' if r['id'] in impl else '○'} | {r['priority']} | "
                f"{SEV_KO[r['severity']]} | {method_ko.get(r['method'], r['method'])} | "
                f"{autofix_ko.get(r['autofix'], r['autofix'])} | {r['title']} | {r['clause']} |"
            )
        lines.append("")
    return "\n".join(lines)


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
    p.set_defaults(func=cmd_check)

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
    p.set_defaults(func=cmd_fix)

    p = sub.add_parser("inspect", help="블록별 역할·번호·스타일 보기(디버깅·시연용)")
    p.add_argument("file", help="입력 docx")
    p.add_argument("--json", action="store_true", help="JSON으로 출력")
    p.add_argument("--all", action="store_true", help="빈 문단과 표 안 문단도 표시")
    p.set_defaults(func=cmd_inspect)

    p = sub.add_parser("rules", help="규칙 목록")
    p.add_argument("--markdown", action="store_true", help="마크다운 표로 출력(docs/RULES.md)")
    p.set_defaults(func=cmd_rules)

    p = sub.add_parser("eval", help="LLM 골드셋 평가(모델 비종속 입증)")
    p.add_argument("--profiles", required=True, help="쉼표로 구분한 프로필 이름")
    p.add_argument(
        "--gold", default=None, help="골드셋 JSONL(기본: tests/llm_gold/modal_verbs.jsonl)"
    )
    p.add_argument("--out", default="docs/eval", help="평가표 출력 디렉터리(기본: docs/eval)")
    p.add_argument("--cache", action="store_true", help="응답 캐시 사용(응답 시간은 정확하지 않음)")
    p.set_defaults(func=cmd_eval)

    p = sub.add_parser("serve", help="로컬 웹 UI")
    p.add_argument("--host", default=None, help="바인딩 주소(기본: 127.0.0.1)")
    p.add_argument("--port", type=int, default=None, help="포트(기본: 8765)")
    p.add_argument("--open", action="store_true", help="브라우저를 자동으로 연다")
    p.set_defaults(func=cmd_serve)

    return parser


def _safe_streams() -> None:
    """출력 인코딩 때문에 죽지 않게 한다.

    콘솔이면 표현 못 하는 문자만 바꾸고(예: cp949의 '⏎'), 파일·파이프로 보낼 때는 UTF-8로 쓴다
    (Windows에서 리다이렉트하면 cp1252가 되어 한국어를 쓰지 못한다).
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream.isatty():
                stream.reconfigure(errors="replace")  # type: ignore[union-attr]
            else:
                stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError, OSError):
            pass


def load_dotenv(path: str = ".env") -> list[str]:
    """현재 디렉터리의 .env(KEY=VALUE)를 환경변수로 읽는다. 이미 지정된 값은 덮어쓰지 않는다."""
    from pathlib import Path

    p = Path(path)
    if not p.is_file():
        return []
    loaded = []
    for line in p.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().removeprefix("export ").strip()
        value = value.strip().strip('"').strip("'")
        if key.isidentifier() and value and key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded


def main(argv: Sequence[str] | None = None) -> int:
    _safe_streams()
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    try:
        return int(args.func(args) or 0)
    except BrokenPipeError:  # 예: ksfix inspect ... | head
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        return 0


if __name__ == "__main__":
    sys.exit(main())
