import sys

import pytest

import pepper


def test_fail_any():
    sys.argv = ["pepper", "--fail-all", "--fail-any", "minion_id", "request"]
    with pytest.raises(SystemExit):
        pepper.script.Pepper()()
