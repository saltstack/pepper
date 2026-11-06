import json
import sys
from unittest.mock import MagicMock, patch

import pytest

import pepper.cli
import pepper.script
from pepper.exceptions import PepperArgumentsException

COMMAND = {"client": "local", "tgt": "*", "fun": "test.ping"}


def _parse(*args):
    sys.argv = ["pepper", *args]
    return pepper.cli.PepperCli().parse_cmd(MagicMock(salt_version=None))


@pytest.mark.parametrize("data", [COMMAND, [COMMAND]], ids=["object", "list"])
def test_json_input(data):
    assert _parse("--json", json.dumps(data)) == [COMMAND]


@pytest.mark.parametrize("data", [COMMAND, [COMMAND, COMMAND]], ids=["object", "list"])
def test_json_file(tmp_path, data):
    path = tmp_path / "command.json"
    path.write_text(json.dumps(data))
    expected = data if isinstance(data, list) else [data]
    assert _parse("--json-file", str(path)) == expected


@pytest.mark.parametrize(
    "data", ['"test.ping"', "[1, 2]", "null"], ids=["string", "numbers", "null"]
)
def test_json_wrong_type(data):
    with pytest.raises(PepperArgumentsException, match="object or a list"):
        _parse("--json", data)


RUNNER_RET = {
    "return": [
        {
            "tag": "salt/run/1/ret",
            "data": {"fun": "runner.test.arg", "return": {"args": ["x"]}, "retcode": 3},
        }
    ]
}


@pytest.mark.parametrize(
    "data,client",
    [
        ({"client": "runner", "fun": "test.arg"}, "runner"),
        (
            [{"client": "runner", "fun": "a"}, {"client": "runner", "fun": "b"}],
            "runner",
        ),
        ([{"client": "runner", "fun": "a"}, {"client": "wheel", "fun": "b"}], "local"),
        ({"fun": "test.arg"}, "local"),
    ],
    ids=["object", "list", "mixed", "no-client"],
)
def test_json_client_sets_output_client(data, client):
    sys.argv = ["pepper", "--json", json.dumps(data)]
    cli = pepper.cli.PepperCli()
    with (
        patch("pepper.cli.PepperCli.login", MagicMock()),
        patch("pepper.cli.PepperCli.low", MagicMock(return_value=RUNNER_RET)),
    ):
        list(cli.run())
    assert cli.options.client == client


def test_json_runner_output_and_exit_code(capsys):
    pytest.importorskip("salt.output")
    sys.argv = ["pepper", "--json", json.dumps({"client": "runner", "fun": "test.arg"})]
    with (
        patch("pepper.cli.PepperCli.login", MagicMock()),
        patch("pepper.cli.PepperCli.low", MagicMock(return_value=RUNNER_RET)),
        patch("salt.output.display_output") as display,
    ):
        assert pepper.script.Pepper()() == 3
    # Unfolded like a runner return, not shown as a minion named "tag"
    assert display.call_args.args[0] == {"args": ["x"]}
