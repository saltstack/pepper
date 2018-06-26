# -*- coding: utf-8 -*-
# Import Python Libraries
from __future__ import absolute_import
import sys

# Import Pepper Libraries
import pepper

# Import Testing Libraries
import pytest


def test_fail_any():
    sys.argv = ['pepper', '--fail-all', '--fail-any', 'minion_id', 'request']
    with pytest.raises(SystemExit):
        pepper.script.Pepper()()
