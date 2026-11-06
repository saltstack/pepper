import sys
from unittest.mock import MagicMock

import pytest

import pepper.cli


def _parse(*args):
    sys.argv = ["pepper", *args]
    return pepper.cli.PepperCli().parse_cmd(MagicMock(salt_version=None))


@pytest.mark.parametrize("client", ["runner", "wheel"])
def test_key_value_is_json_or_string(client):
    # The README documents that values are JSON, not YAML as with salt-run
    (low,) = _parse(
        f"--client={client}",
        "test.arg",
        "one=true",
        "two=True",
        'three={"hello": "world"}',
        "four=[a, b]",
    )
    assert low["one"] is True
    assert low["two"] == "True"
    assert low["three"] == {"hello": "world"}
    assert low["four"] == "[a, b]"
