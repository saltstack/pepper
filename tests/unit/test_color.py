import sys
from unittest.mock import MagicMock, patch

import pytest

import pepper.script

pytest.importorskip("salt.output")

RESULT = {"return": [{"minion": {"ret": {"key": "value"}, "retcode": 0}}]}


@pytest.fixture
def run(capsys, monkeypatch):
    def _run(*args, tty=False):
        monkeypatch.setattr("salt.output.os.isatty", lambda fd: tty)
        sys.argv = ["pepper", *args, "*", "test.ping"]
        with (
            patch("pepper.cli.PepperCli.login", MagicMock()),
            patch("pepper.cli.PepperCli.low", MagicMock(return_value=RESULT)),
        ):
            pepper.script.Pepper()()
        return capsys.readouterr().out

    return _run


def _colored(text):
    return "\x1b[" in text


def test_terminal_is_colored(run):
    assert _colored(run(tty=True))


def test_pipe_is_not_colored(run):
    assert not _colored(run(tty=False))


def test_no_color(run):
    assert not _colored(run("--no-color", tty=True))
    assert not _colored(run("--no-colour", tty=True))


def test_force_color(run):
    assert _colored(run("--force-color", tty=False))


def test_output_file_is_not_colored(run, tmp_path):
    out = tmp_path / "out"
    run(f"--output-file={out}", tty=True)
    assert "key" in out.read_text()
    assert not _colored(out.read_text())


def test_output_file_force_color(run, tmp_path):
    out = tmp_path / "out"
    run(f"--output-file={out}", "--force-color", tty=False)
    assert _colored(out.read_text())
