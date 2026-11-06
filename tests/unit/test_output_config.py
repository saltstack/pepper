import json
import sys
from unittest.mock import MagicMock, patch

import pytest

import pepper.script

pytest.importorskip("salt.output")

RESULT = {"return": [{"minion": {"ret": {"key": "value"}, "retcode": 0}}]}


@pytest.fixture
def run(capsys, tmp_path):
    master = tmp_path / "master"

    def _run(config, *args):
        master.write_text(config)
        sys.argv = ["pepper", "-m", str(master), *args, "*", "test.ping"]
        with (
            patch("pepper.cli.PepperCli.login", MagicMock()),
            patch("pepper.cli.PepperCli.low", MagicMock(return_value=RESULT)),
        ):
            pepper.script.Pepper()()
        return capsys.readouterr().out

    return _run


def test_output_from_master_config(run):
    assert json.loads(run("output: json\n")) == {"minion": {"key": "value"}}


def test_out_option_overrides_master_config(run):
    assert run("output: json\n", "--out=yaml") == "minion:\n  key: value\n"


def test_no_color_from_master_config(run, monkeypatch):
    monkeypatch.setattr("salt.output.os.isatty", lambda fd: True)
    assert "\x1b[" in run("")
    assert "\x1b[" not in run("no_color: true\n")
