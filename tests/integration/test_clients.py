# -*- coding: utf-8 -*-
import json
import os
import pytest


def test_local_bad_opts(pepper_cli):
    with pytest.raises(SystemExit):
        pepper_cli('*')
    with pytest.raises(SystemExit):
        pepper_cli('test.ping')
    with pytest.raises(SystemExit):
        pepper_cli('--client=ssh', 'test.ping')
    with pytest.raises(SystemExit):
        pepper_cli('--client=ssh', '*')


def test_runner_client(pepper_cli):
    ret = pepper_cli(
        '--client=runner', 'test.arg',
        'one', 'two=what',
        'three={0}'.format(json.dumps({"hello": "world"})),
    )
    assert ret == {"runner": {"args": ["one"], "kwargs": {"three": {"hello": "world"}, "two": "what"}}}


def test_wheel_client_arg(pepper_cli, session_minion_id):
    ret = pepper_cli(
        '--client=wheel', 'minions.connected', session_minion_id
    )
    assert ret['success'] is True


def test_wheel_client_kwargs(pepper_cli, session_master_config_file):
    ret = pepper_cli(
        '--client=wheel', 'config.update_config', 'file_name=pepper',
        'yaml_contents={0}'.format(json.dumps({"timeout": 5})),
    )
    assert ret['return'] == 'Wrote pepper.conf'
    assert os.path.isfile('{0}.d/pepper.conf'.format(session_master_config_file))


@pytest.mark.xfail
def test_ssh_client(pepper_cli, session_roster_config, session_roster_config_file):
    ret = pepper_cli('--client=ssh', '*', 'test.ping')
    assert ret['ssh']['localhost']['return'] is True


def test_bad_client(pepper_cli):
    ret = pepper_cli('--client=whatever')
    assert ret == 1
