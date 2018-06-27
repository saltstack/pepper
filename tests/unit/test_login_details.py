# -*- coding: utf-8 -*-
from __future__ import absolute_import
import sys

# Import Pepper Libs
import pepper.cli

# Import Testing libraries
from mock import MagicMock, patch


def test_interactive_logins(pepperrc):
    sys.argv = ['pepper', '-c', pepperrc, '-p', 'noopts']

    with patch(
             'pepper.cli.input',
             MagicMock(return_value='pepper')
         ), patch(
             'pepper.cli.getpass.getpass',
             MagicMock(return_value='pepper')
         ):
        result = pepper.cli.PepperCli().get_login_details()
    assert result['SALTAPI_USER'] is 'pepper'
    assert result['SALTAPI_PASS'] is 'pepper'
