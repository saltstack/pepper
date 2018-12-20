# -*- coding: utf-8 -*-
# Import Python Libraries
from __future__ import print_function, unicode_literals, absolute_import
import imp
import os
import shutil
import subprocess

# Import Pepper Libraries
import pepper


def test_no_setup():
    setuppath = os.path.join(os.path.dirname(pepper.__file__), os.pardir, 'setup.py')
    shutil.move(setuppath, setuppath + '.bak')
    ptest = imp.load_source('ptest', os.path.join(os.path.dirname(pepper.__file__), '__init__.py'))
    shutil.move(setuppath + '.bak', setuppath)
    assert ptest.version is None
    assert ptest.sha is None


def test_version():
    version = subprocess.check_output(['git', 'describe']).split(b'-')
    version = b'.'.join([version[0], b'dev' + version[1]]).decode()
    sha = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).strip().decode()
    assert pepper.version == version
    assert ptest.sha is None
