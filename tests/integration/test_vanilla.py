# -*- coding: utf-8 -*-
import pytest


def test_local(pepper_cli, session_minion_id):
    '''Sanity-check: Has at least one minion - /run - /login query type is parameterized'''
    ret = pepper_cli('*', 'test.ping')
    assert ret[session_minion_id] is True


@pytest.mark.xfail(
    pytest.config.getoption("--salt-api-backend") == "rest_tornado",
    reason="this is broken in rest_tornado until future release",
)
def test_long_local(pepper_cli, session_minion_id):
    '''Test a long call blocks until the return'''
    ret = pepper_cli('--timeout=60', '*', 'test.sleep', '30')
    assert ret[session_minion_id] is True
