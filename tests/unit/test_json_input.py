import json
import sys
from unittest.mock import MagicMock

import pytest

import pepper.cli
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
