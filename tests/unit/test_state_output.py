import sys
from unittest.mock import MagicMock, patch

import pytest

import pepper.script

pytest.importorskip("salt.output")

STATE_RET = {
    "return": [
        {
            "minion": {
                "jid": "20261105120000000000",
                "out": "highstate",
                "retcode": 0,
                "ret": {
                    "test_|-unchanged_|-unchanged_|-succeed_without_changes": {
                        "__id__": "unchanged",
                        "__run_num__": 0,
                        "__sls__": "demo",
                        "changes": {},
                        "comment": "Success!",
                        "duration": 1.0,
                        "name": "unchanged",
                        "result": True,
                        "start_time": "12:00:00.000000",
                    }
                },
            }
        }
    ]
}


def _output(capsys, *args):
    sys.argv = ["pepper", *args, "*", "state.apply"]
    with (
        patch("pepper.cli.PepperCli.login", MagicMock()),
        patch("pepper.cli.PepperCli.low", MagicMock(return_value=STATE_RET)),
    ):
        pepper.script.Pepper()()
    return capsys.readouterr().out


@pytest.mark.parametrize(
    "args,opts",
    [
        (["--state-output=terse"], {"state_output": "terse"}),
        (["--state_output=mixed_id"], {"state_output": "mixed_id"}),
        (["--state-verbose=False"], {"state_verbose": False}),
        (["--state-verbose=true"], {"state_verbose": True}),
    ],
)
def test_state_opts(args, opts):
    sys.argv = ["pepper", "*", "state.apply"]
    defaults = pepper.script.Pepper().opts
    sys.argv = ["pepper", *args, "*", "state.apply"]
    salt_opts = pepper.script.Pepper().opts
    for key in ("state_output", "state_verbose"):
        assert salt_opts.get(key) == opts.get(key, defaults.get(key))


def test_state_output_terse(capsys):
    full = _output(capsys)
    terse = _output(capsys, "--state-output=terse")
    assert "Comment: Success!" in full
    assert "Comment: Success!" not in terse
    assert "Result: Clean" in terse


def test_state_verbose_false(capsys):
    assert "unchanged" in _output(capsys)
    assert "Success!" not in _output(capsys, "--state-verbose=false")
