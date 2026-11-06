import importlib.util
import os
from importlib.metadata import PackageNotFoundError, version
from unittest.mock import patch

import pepper


def _load_pepper_init(name):
    """
    Execute a fresh copy of pepper/__init__.py without touching the imported module
    """
    path = os.path.join(os.path.dirname(pepper.__file__), "__init__.py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_version():
    assert pepper.__version__ == version("salt_pepper")
    assert pepper.version == pepper.__version__
    assert pepper.sha is None


def test_version_not_installed():
    with patch("importlib.metadata.version", side_effect=PackageNotFoundError):
        ptest = _load_pepper_init("ptest")
    assert ptest.__version__ is None
    assert ptest.version is None
    assert ptest.sha is None
