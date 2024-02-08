import json
import sys
from unittest.mock import MagicMock
from unittest.mock import mock_open
from unittest.mock import patch

import pepper.cli

# Import Pepper Libraries
# Import Testing Libraries


def test_token():
    sys.argv = ["pepper", "*", "test.ping"]
    client = pepper.cli.PepperCli()
    client.options.mktoken = True
    mock_data = (
        '{"perms": [".*", "@runner", "@wheel", "@jobs"], "start": 1529967752.516165, '
        '"token": "7130faa1e17f935d5f2702465cafdc73212d64d0", "expire": 1529968905.1131861, '
        '"user": "pepper", "eauth": "pam"}\n'
    )
    mock_api = MagicMock()
    mock_api.login = MagicMock(return_value=mock_data)
    with patch("pepper.cli.open", mock_open(read_data=mock_data)), patch(
        "pepper.cli.PepperCli.get_login_details", MagicMock(return_value=mock_data)
    ), patch("pepper.cli.PepperCli.parse_login", MagicMock(return_value={})), patch(
        "os.remove", MagicMock(return_value=None)
    ), patch(
        "json.dump", MagicMock(side_effect=Exception("Test Error"))
    ):
        ret1 = client.login(mock_api)
        with patch("os.path.isfile", MagicMock(return_value=False)):
            ret2 = client.login(mock_api)
        with patch("time.time", MagicMock(return_value=1529968044.133632)):
            ret3 = client.login(mock_api)
    assert json.loads(ret1) == json.loads(mock_data)
    assert json.loads(ret2) == json.loads(mock_data)
    assert ret3 == json.loads(mock_data)
