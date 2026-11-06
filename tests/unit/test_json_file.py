import sys
from unittest.mock import MagicMock

import pytest

import pepper.cli
from pepper.exceptions import PepperArgumentsException


def test_json_file_not_utf8(tmp_path):
    path = tmp_path / "command.json"
    path.write_bytes(b'[{"client": "local", "tgt": "\\xff\xff"}]')
    sys.argv = ["pepper", "--json-file", str(path)]
    cli = pepper.cli.PepperCli()
    with pytest.raises(PepperArgumentsException, match="Invalid JSON given"):
        cli.parse_cmd(MagicMock())
