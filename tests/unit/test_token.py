# -*- coding: utf-8 -*-
from __future__ import absolute_import

import json
import sys

# Import Testing Libraries
from mock import MagicMock, mock_open, patch

# Import Pepper Libraries
import pepper.cli


def test_token():
    sys.argv = ["pepper", "*", "test.ping"]
    client = pepper.cli.PepperCli()
    client.options.mktoken = True
    mock_data = {
        "perms": [".*", "@runner", "@wheel", "@jobs"],
        "start": 1529967752.516165,
        "token": "7130faa1e17f935d5f2702465cafdc73212d64d0",
        "expire": 1529968905.1131861,
        "user": "pepper",
        "eauth": "pam",
    }
    mock_data_json = json.dumps(mock_data)

    mock_api = MagicMock()
    mock_api.login = MagicMock(return_value=mock_data_json)

    with patch("pepper.cli.open", mock_open(read_data=mock_data_json)), patch(
        "pepper.cli.PepperCli.get_login_details", MagicMock(return_value=mock_data)
    ), patch("os.remove", MagicMock(return_value=None)), patch(
        "json.dump", MagicMock(side_effect=Exception("Test Error"))
    ):
        ret1 = client.login(mock_api, mock_data)
        with patch("os.path.isfile", MagicMock(return_value=False)):
            ret2 = client.login(mock_api, mock_data)
        with patch("time.time", MagicMock(return_value=1529968044.133632)):
            ret3 = client.login(mock_api, mock_data)

    assert json.loads(ret1) == mock_data
    assert json.loads(ret2) == mock_data
    assert ret3 == mock_data
