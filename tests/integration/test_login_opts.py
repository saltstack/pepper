# -*- coding: utf-8 -*-
from __future__ import absolute_import


def test_cli_opts(pepper_cli, session_minion_id, salt_api_port):
    '''Test the using a profile'''
    ret = pepper_cli(
        '--saltapi-url=http://localhost:{0}/'.format(salt_api_port),
        '--eauth=sharedsecret',
        '--username=pepper',
        '--password=pepper',
        '*', 'test.ping',
        profile='noprofile',
    )
    assert ret[session_minion_id] is True


def test_cli_opts_not_in_profile(pepper_cli, session_minion_id, salt_api_port):
    '''Test the using a profile'''
    ret = pepper_cli(
        '--eauth=sharedsecret',
        '--username=pepper',
        '--password=pepper',
        '*', 'test.ping',
        profile='noopts',
    )
    assert ret[session_minion_id] is True


def test_cli_api_not_in_profile(pepper_cli, session_minion_id, salt_api_port):
    '''Test the using a profile'''
    ret = pepper_cli(
        '--saltapi-url=http://localhost:{0}/'.format(salt_api_port),
        '*', 'test.ping',
        profile='noapi',
    )
    assert ret[session_minion_id] is True


def test_no_username(pepper_cli, session_minion_id, salt_api_port):
    '''Test the using a profile'''
    ret = pepper_cli(
        '--non-interactive',
        '*', 'test.ping',
        profile='noopts',
    )
    assert ret == 1


def test_no_password(pepper_cli, session_minion_id, salt_api_port):
    '''Test the using a profile'''
    ret = pepper_cli(
        '--username=pepper',
        '--non-interactive',
        '*', 'test.ping',
        profile='noopts',
    )
    assert ret == 1
