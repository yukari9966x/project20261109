#!/usr/bin/env python3
"""브라우저 데모(GitHub Pages) 빌드: webapp/ + ksfix 휠 + python-docx 휠 → site/.

같은 webapp/을 쓰되 엔진만 engine-server.js → engine-pyodide.js로 바꾼다.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYODIDE_VERSION = "0.27.2"
SERVER_NOTE = "문서는 이 컴퓨터의 KS-Fix 로컬 서버에서만 처리됩니다(LLM 끔: 외부 전송 없음)."
BROWSER_NOTE = (
    "문서는 이 브라우저 안에서만 처리됩니다(서버로 보내지 않음). "
    "첫 실행 때 처리 엔진(Pyodide)을 내려받아 20~40초쯤 걸립니다. AI(LLM) 기능은 로컬 실행판에서 쓸 수 있습니다."
)


def rewrite_index(html: str) -> str:
    """서버판 index.html → 브라우저 데모판(엔진 스크립트·안내 문구 교체)."""
    html = html.replace(
        '<script src="engine-server.js"></script>', '<script src="engine-pyodide.js"></script>'
    )
    html = html.replace(SERVER_NOTE, BROWSER_NOTE)
    return html.replace(
        "파일은 1시간 동안 보관됩니다.", "파일은 이 브라우저 안에서만 만들어집니다."
    )


def build(out: Path) -> Path:
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(ROOT / "webapp", out)
    wheels = out / "wheels"
    wheels.mkdir()
    pip = [sys.executable, "-m", "pip"]
    subprocess.run([*pip, "wheel", "--no-deps", "-q", "-w", str(wheels), str(ROOT)], check=True)
    subprocess.run(
        [
            *pip,
            "download",
            "--no-deps",
            "--only-binary=:all:",
            "-q",
            "-d",
            str(wheels),
            "python-docx==1.2.0",
        ],
        check=True,
    )
    names = sorted(p.name for p in wheels.glob("*.whl"))
    manifest = {"wheels": names, "pyodide": PYODIDE_VERSION}
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    index = out / "index.html"
    index.write_text(rewrite_index(index.read_text(encoding="utf-8")), encoding="utf-8")
    (out / "engine-server.js").unlink()
    (out / ".nojekyll").write_text("", encoding="utf-8")
    samples = out / "samples"
    samples.mkdir()
    for p in sorted((ROOT / "samples").glob("*.docx")):
        shutil.copy(p, samples / p.name)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="브라우저 데모 빌드")
    ap.add_argument("-o", "--out", default=str(ROOT / "site"))
    args = ap.parse_args(argv)
    out = build(Path(args.out))
    print(f"브라우저 데모: {out} (python -m http.server --directory {out} 로 확인)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
