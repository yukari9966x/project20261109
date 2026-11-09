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
    proc = subprocess.run(
        [sys.executable, "-m", "ksfix", "--version"], capture_output=True, text=True, check=True
    )
    assert proc.stdout.strip() == f"ksfix {__version__}"
