# -*- coding: utf-8 -*-


def test_local_poll(pepper_cli, session_minion_id):
    '''Test the returns poller for localclient'''
    ret = pepper_cli('--fail-if-incomplete', '*', 'test.sleep', '1')
    assert ret[session_minion_id] is True
    assert len(ret) == 1


def test_local_poll_long(pepper_cli, session_minion_id):
    '''Test the returns poller for localclient'''
    ret = pepper_cli('--fail-if-incomplete', '*', 'test.sleep', '30')
    assert ret[session_minion_id] is True
    assert len(ret) == 1


def test_local_poll_timeout(pepper_cli, session_minion_id):
    '''Test the returns poller for localclient'''
    ret = pepper_cli('--timeout=5', '--fail-if-incomplete', '*', 'test.sleep', '30')
    assert ret == {'Failed': [session_minion_id]}
