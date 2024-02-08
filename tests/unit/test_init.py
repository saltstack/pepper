# Import Python Libraries
import imp
import os
import shutil

import setuptools_scm

import pepper

# Import Pepper Libraries


def test_no_setup():
    setuppath = os.path.join(os.path.dirname(pepper.__file__), os.pardir, "setup.py")
    shutil.move(setuppath, setuppath + ".bak")
    ptest = imp.load_source("ptest", os.path.join(os.path.dirname(pepper.__file__), "__init__.py"))
    shutil.move(setuppath + ".bak", setuppath)
    assert ptest.version == setuptools_scm.get_version()
    assert ptest.sha is None


def test_version():
    assert pepper.version == setuptools_scm.get_version()
    assert pepper.sha is None
