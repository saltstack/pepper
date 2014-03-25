'''
Pepper is a CLI front-end to salt-api

'''
import json
import os

from pepper.libpepper import Pepper

__all__ = ('__version__', 'Pepper')

try:
    # First try to grab the version from the version.json build file.
    vfile = os.path.join(os.path.dirname(__file__), 'version.json')

    with open(vfile, 'rb') as f:
        version = json.load(f).get('version')
except IOError:
    # Build version file doesn't exist; we may be running from a clone.
    setup_file = os.path.join(os.path.dirname(__file__), os.pardir, 'setup.py')

    if os.path.exists(setup_file):
        import imp

        setup = imp.load_source('pepper_setup', setup_file)
        version = setup.read_version_tag()
    else:
        version = 'Unknown'

__version__ = version or 'Unknown'
