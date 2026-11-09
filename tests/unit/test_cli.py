import subprocess
import sys

import pytest

from ksfix import __version__
from ksfix.cli import build_parser, main


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_help_lists_commands(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])
    out = capsys.readouterr().out
    for cmd in ("check", "fix", "inspect", "rules", "eval", "serve"):
        assert cmd in out


def test_no_command_prints_help(capsys):
    assert main([]) == 0
    assert "ksfix" in capsys.readouterr().out


def test_parser_defaults():
    args = build_parser().parse_args(["fix", "a.docx"])
    assert args.mode == "tracked"
    assert args.out == "out"


def test_module_entrypoint():
    proc = subprocess.run(  # nosemgrep  (고정 인자로 현재 파이썬의 ksfix 실행)
        [sys.executable, "-m", "ksfix", "--version"], capture_output=True, text=True, check=True
    )
    assert proc.stdout.strip() == f"ksfix {__version__}"


def test_load_dotenv_does_not_override(tmp_path, monkeypatch):
    from ksfix.cli import load_dotenv

    env = tmp_path / ".env"
    env.write_text(
        "# 주석\nKSFIX_TEST_A=1\nexport KSFIX_TEST_B='두 번째'\nKSFIX_TEST_C=\nKSFIX_TEST_D=새 값\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("KSFIX_TEST_D", "기존 값")
    for k in ("KSFIX_TEST_A", "KSFIX_TEST_B", "KSFIX_TEST_C"):
        monkeypatch.delenv(k, raising=False)
    loaded = load_dotenv(str(env))
    import os

    assert loaded == ["KSFIX_TEST_A", "KSFIX_TEST_B"]
    assert os.environ["KSFIX_TEST_B"] == "두 번째" and os.environ["KSFIX_TEST_D"] == "기존 값"
    assert "KSFIX_TEST_C" not in os.environ
    for k in loaded:
        monkeypatch.delenv(k)
