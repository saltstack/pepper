# -*- coding: utf-8 -*-
import json
import time


def test_local_token(tokfile, pepper_cli, session_minion_id):
    '''Test local execution with token file'''
    ret = pepper_cli('-x', tokfile, '--make-token', '--run-uri', '*', 'test.ping')
    assert ret['return'][0][session_minion_id]['ret'] is True


def test_runner_token(tokfile, pepper_cli):
    '''Test runner execution with token file'''
    ret = pepper_cli('-x', tokfile, '--make-token', '--run-uri', '--client', 'runner', 'test.metasyntactic')
    exps = [
        'foo', 'bar', 'baz', 'qux', 'quux', 'quuz', 'corge', 'grault',
        'garply', 'waldo', 'fred', 'plugh', 'xyzzy', 'thud'
    ]
    assert all(exp in ret['return'][0] for exp in exps)


def test_token_expire(tokfile, pepper_cli):
    '''Test token override param'''
    now = time.time()
    pepper_cli('-x', tokfile, '--make-token', '--run-uri',
               '--token-expire', '94670856',
               '*', 'test.ping')

    with open(tokfile, 'r') as tfile:
        token = json.load(tfile)
        diff = (now + float(94670856)) - token['expire']
        # Allow for 10-second window between request and master-side auth.
        assert diff < 10
