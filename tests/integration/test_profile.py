# -*- coding: utf-8 -*-


def test_config_profile(pepper_cli, session_minion_id):
    '''Test the using a profile'''
    ret = pepper_cli('*', 'test.ping', profile='pepper')
    assert ret[session_minion_id] is True
