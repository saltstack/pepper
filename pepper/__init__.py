'''
Pepper is a CLI front-end to salt-api

'''
import json
import os

from pepper.libpepper import Pepper, PepperException

__all__ = ('__version__', '__gitrev__', 'Pepper', 'PepperException')

try:
    # First try to grab the version from the version.json build file.
    vfile = os.path.join(os.path.dirname(__file__), 'version.json')

    with open(vfile, 'r') as f:
        ret = json.load(f)
        version = ret.get('version')
        sha = ret.get('sha')
except IOError:
    # Build version file doesn't exist; we may be running from a clone.
    setup_file = os.path.join(os.path.dirname(__file__), os.pardir, 'setup.py')

    if os.path.exists(setup_file):
        import imp

        setup = imp.load_source('pepper_setup', setup_file)
        version, sha = setup.get_version()
    else:
        version, sha = None, None

__version__ = version or 'Unknown'
__gitrev__ = sha
