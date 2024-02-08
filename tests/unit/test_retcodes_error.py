# Import Python Libraries
import sys

import pytest

import pepper

# Import Pepper Libraries
# Import Testing Libraries


def test_fail_any():
    sys.argv = ["pepper", "--fail-all", "--fail-any", "minion_id", "request"]
    with pytest.raises(SystemExit):
        pepper.script.Pepper()()
