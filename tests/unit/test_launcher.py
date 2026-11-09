"""Windows 실행파일 런처: 소스 상태에서 자체 점검·포트 선택·CLI 위임."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load():
    spec = importlib.util.spec_from_file_location(
        "ksfix_launcher", ROOT / "packaging" / "launcher.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_selftest_passes(capsys):
    assert load().selftest() == 0
    out = capsys.readouterr().out
    assert out.count("[통과]") == 7 and "[실패]" not in out


def test_free_port_and_cli_delegation(capsys):
    mod = load()
    assert isinstance(mod.free_port(0), int)
    assert mod.main(["rules"]) == 0
    assert "KS A 0001" in capsys.readouterr().out
