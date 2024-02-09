import sys
from unittest.mock import MagicMock
from unittest.mock import patch

import pepper.cli

# Import Testing libraries


def test_interactive_logins():
    sys.argv = ["pepper", "-c", "tests/.pepperrc", "-p", "noopts"]

    with patch("pepper.cli.input", MagicMock(return_value="pepper")), patch(
        "pepper.cli.getpass.getpass", MagicMock(return_value="pepper")
    ):
        result = pepper.cli.PepperCli().get_login_details()
    assert result["SALTAPI_USER"] == "pepper"
    assert result["SALTAPI_PASS"] == "pepper"
