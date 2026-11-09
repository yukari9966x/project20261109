"""브라우저 데모 빌드: 같은 UI에서 엔진 스크립트와 안내 문구만 바뀌는지."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_rewrite_index_swaps_engine_and_notice():
    spec = importlib.util.spec_from_file_location(
        "build_pages", ROOT / "scripts" / "build_pages.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    html = (ROOT / "webapp" / "index.html").read_text(encoding="utf-8")
    out = mod.rewrite_index(html)
    assert "engine-pyodide.js" in out and "engine-server.js" not in out
    assert "브라우저 안에서만 처리" in out and "로컬 서버에서만" not in out
    assert out.count("<script") == html.count("<script")


def test_worker_pins_pyodide_version():
    worker = (ROOT / "webapp" / "pyodide-worker.js").read_text(encoding="utf-8")
    assert 'PYODIDE_VERSION = "0.27.2"' in worker
    assert "ksfix.api" in worker
