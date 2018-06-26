# -*- coding: utf-8 -*-
import salt.utils.yaml as yaml


def test_local_poll(pepper_cli, session_minion_id):
    '''Test the returns poller for localclient'''
    ret = pepper_cli('--run-uri', '--fail-if-incomplete', '*', 'test.sleep', '1')
    assert ret[0][session_minion_id] is True
    assert ret[1] == {'Failed': []}


def test_local_poll_long(pepper_cli, session_minion_id):
    '''Test the returns poller for localclient'''
    ret = pepper_cli('--run-uri', '--fail-if-incomplete', '*', 'test.sleep', '30')
    assert ret[0][session_minion_id] is True
    assert ret[1] == {'Failed': []}


def test_local_poll_timeout(pepper_cli, session_minion_id):
    '''Test the returns poller for localclient'''
    ret = pepper_cli('--run-uri', '--timeout=5', '--fail-if-incomplete', '*', 'test.sleep', '10')
    assert yaml.load(ret) == {'Failed': [session_minion_id]}
