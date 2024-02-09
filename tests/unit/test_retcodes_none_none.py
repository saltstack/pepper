# Import Python Libraries
import sys
from unittest.mock import MagicMock
from unittest.mock import patch

import pepper

# Import Pepper Libraries

PAYLOAD = {
    "return": [
        {
            "saltstack.ezh.msk.ru": {
                "jid": "20180414193904158892",
                "ret": "Hello from SaltStack",
            },
            "ezh.msk.ru": {
                "jid": "20180414193904158892",
                "ret": "Hello from SaltStack",
            },
        }
    ]
}


@patch("pepper.cli.PepperCli.login", MagicMock(side_effect=lambda arg: None))
@patch("pepper.cli.PepperCli.low", MagicMock(side_effect=lambda api, load: PAYLOAD))
def test_default():
    sys.argv = ["pepper", "minion_id", "request"]
    ret_code = pepper.script.Pepper()()
    assert ret_code == 0


@patch("pepper.cli.PepperCli.login", MagicMock(side_effect=lambda arg: None))
@patch("pepper.cli.PepperCli.low", MagicMock(side_effect=lambda api, load: PAYLOAD))
def test_fail_any():
    sys.argv = ["pepper", "--fail-any", "minion_id", "request"]
    ret_code = pepper.script.Pepper()()
    assert ret_code == 0


@patch("pepper.cli.PepperCli.login", MagicMock(side_effect=lambda arg: None))
@patch("pepper.cli.PepperCli.low", MagicMock(side_effect=lambda api, load: PAYLOAD))
def test_fail_any_none():
    sys.argv = ["pepper", "--fail-any-none", "minion_id", "request"]
    ret_code = pepper.script.Pepper()()
    assert ret_code == -1


@patch("pepper.cli.PepperCli.login", MagicMock(side_effect=lambda arg: None))
@patch("pepper.cli.PepperCli.low", MagicMock(side_effect=lambda api, load: PAYLOAD))
def test_fail_all():
    sys.argv = ["pepper", "--fail-all", "minion_id", "request"]
    ret_code = pepper.script.Pepper()()
    assert ret_code == 0


@patch("pepper.cli.PepperCli.login", MagicMock(side_effect=lambda arg: None))
@patch("pepper.cli.PepperCli.low", MagicMock(side_effect=lambda api, load: PAYLOAD))
def test_fail_all_none():
    sys.argv = ["pepper", "--fail-all-none", "minion_id", "request"]
    ret_code = pepper.script.Pepper()()
    assert ret_code == -1
