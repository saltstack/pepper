# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import shutil
import tempfile


def test_local_json(pepper_cli, session_minion_id):
    json = '[{"tgt": "*", "fun": "test.ping", "client": "local"}]'
    ret = pepper_cli('--json', json)
    assert ret[session_minion_id] is True


def test_local_json_bad(pepper_cli):
    json = '{what}'
    ret = pepper_cli('--json', json)
    assert ret == 1


def test_local_json_file(pepper_cli, session_minion_id):
    tmpjson = os.path.join(tempfile.mkdtemp(), 'json')
    with open(tmpjson, 'w') as tmpfile:
        print(
            '[{"client": "local", "tgt": "*", "fun": "test.ping"}]',
            file=tmpfile,
        )
    ret = pepper_cli('--json-file', tmpjson)
    shutil.rmtree(os.path.dirname(tmpjson))
    assert ret[session_minion_id] is True


def test_local_json_file_bad(pepper_cli):
    tmpjson = os.path.join(tempfile.mkdtemp(), 'json')
    with open(tmpjson, 'w') as tmpfile:
        print(
            '{what}',
            file=tmpfile,
        )
    ret = pepper_cli('--json-file', tmpjson)
    shutil.rmtree(os.path.dirname(tmpjson))
    assert ret == 1


def test_local_json_no_file(pepper_cli):
    ret = pepper_cli('--json-file', '/tmp/wahteverfile')
    assert ret == 1
