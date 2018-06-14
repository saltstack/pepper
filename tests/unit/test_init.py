# -*- coding: utf-8 -*-
# Import Python Libraries
from __future__ import print_function, unicode_literals, absolute_import
import imp
import os
import subprocess

# Import Pepper Libraries
import pepper


def test_version():
    version = subprocess.check_output(['git', 'describe']).split(b'-')
    version = b'.'.join([version[0], b'dev' + version[1]]).decode()
    sha = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).strip().decode()
    assert pepper.version == version
    assert pepper.sha == sha


def test_version_json():
    vfile = os.path.join(os.path.dirname(pepper.__file__), 'version.json')
    with open(vfile, 'w') as vfh:
        print('{"version": "9999.99.9", "sha": "abc123"}', file=vfh)

    ptest = imp.load_source('ptest', os.path.join(os.path.dirname(pepper.__file__), '__init__.py'))
    os.remove(vfile)
    assert ptest.version == '9999.99.9'
    assert ptest.sha == 'abc123'
