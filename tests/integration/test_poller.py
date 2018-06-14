# -*- coding: utf-8 -*-

import logging
log = logging.getLogger(__name__)


def test_local_poll(pepper_cli, session_minion_id):
    '''Test the returns poller for localclient'''
    ret = pepper_cli('--run-uri', '--fail-if-incomplete', '*', 'test.sleep', '30')
    assert ret[0][session_minion_id] is True
    assert ret[1] == {'Failed': []}
