import json
import sys
from unittest.mock import MagicMock, patch

import pytest

import pepper.script

PAYLOAD = {
    "return": [
        {
            "failed": {"jid": "20180414193904158892", "ret": "nope", "retcode": 127},
            "passed": {"jid": "20180414193904158892", "ret": True, "retcode": 0},
        }
    ]
}

NO_RETCODES = {"return": [{"minion": {"jid": "20180414193904158892", "ret": True}}]}


@pytest.fixture(autouse=True)
def without_salt(monkeypatch):
    monkeypatch.setattr(pepper.script, "HAS_SALT", False)


@pytest.mark.parametrize(
    "option,payload,expected",
    [
        (None, PAYLOAD, 1),
        ("--fail-any", PAYLOAD, 127),
        ("--fail-any-none", PAYLOAD, 127),
        ("--fail-all", PAYLOAD, 0),
        ("--fail-all-none", PAYLOAD, 0),
        ("--fail-any-none", NO_RETCODES, -1),
        ("--fail-all-none", NO_RETCODES, -1),
    ],
)
def test_validate_without_salt(capsys, option, payload, expected):
    sys.argv = ["pepper"] + ([option] if option else []) + ["minion_id", "request"]
    with (
        patch("pepper.cli.PepperCli.login", MagicMock()),
        patch("pepper.cli.PepperCli.low", MagicMock(return_value=payload)),
    ):
        assert pepper.script.Pepper()() == expected
    # The JSON output is unchanged
    assert json.loads(capsys.readouterr().out) == payload
