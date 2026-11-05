import itertools
import json
import sys
from unittest.mock import MagicMock, patch

import pytest

import pepper.script

ASYNC_RET = {"return": [{"jid": "20261105120000000000", "minions": ["a", "b"]}]}


@pytest.fixture(autouse=True)
def without_salt(monkeypatch):
    monkeypatch.setattr(pepper.script, "HAS_SALT", False)
    monkeypatch.setattr(pepper.cli.time, "sleep", MagicMock())


def _run(capsys, *args, low_returns):
    sys.argv = ["pepper", "--fail-if-incomplete", *args]
    low = MagicMock(side_effect=low_returns)
    with (
        patch("pepper.cli.PepperCli.login", MagicMock()),
        patch("pepper.cli.PepperCli.low", low),
    ):
        exit_code = pepper.script.Pepper()()
    out, err = capsys.readouterr()
    return exit_code, out, err, low


def test_returns_are_one_json_document(capsys):
    exit_code, out, _, low = _run(
        capsys,
        "*",
        "test.ping",
        low_returns=[
            ASYNC_RET,
            {"return": [{"a": True}]},
            {"return": [{"a": True, "b": True}]},
        ],
    )
    assert exit_code == 0
    assert json.loads(out) == {"return": [{"a": True}, {"b": True}]}
    assert low.call_args_list[0].args[1][0]["client"] == "local_async"
    lookup = low.call_args_list[1].args[1][0]
    assert lookup["fun"] == "jobs.lookup_jid"


@pytest.mark.parametrize("fail_option", ["--fail-any-none", "--fail-all-none"])
def test_fail_none_options_with_poller(capsys, fail_option):
    # The poller's results have no retcodes, so the --fail-* options cannot
    # make a complete poll fail
    exit_code, _, _, _ = _run(
        capsys,
        fail_option,
        "*",
        "test.ping",
        low_returns=[ASYNC_RET, {"return": [{"a": True, "b": True}]}],
    )
    assert exit_code == 0


def test_missing_minions_fail(capsys, monkeypatch):
    # A clock that always moves on, so --timeout=0 has passed at the first check
    monkeypatch.setattr(pepper.cli.time, "time", itertools.count().__next__)
    exit_code, out, _, _ = _run(
        capsys, "--timeout=0", "*", "test.ping", low_returns=[ASYNC_RET]
    )
    assert exit_code == 1
    assert json.loads(out) == {"return": [{"Failed": ["a", "b"]}]}


@pytest.mark.parametrize(
    "args",
    [
        ["--client=runner", "test.arg"],
        ["--batch=10%", "*", "test.ping"],
        ["--client=ssh", "*", "test.ping"],
    ],
    ids=["runner", "batch", "ssh"],
)
def test_rejects_other_clients(capsys, args):
    exit_code, out, err, low = _run(capsys, *args, low_returns=[])
    assert exit_code == 1
    assert "--fail-if-incomplete only works with" in err
    low.assert_not_called()
