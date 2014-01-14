'''
Helper utils for using Pepper from the CLI

A central place to store repeat functionality between all the pepper scripts
(salt, salt-run, pepper, etc) such as common CLI flags (logging level).

As well as common operations such as reading/writing the auth token to a file.

'''
import ConfigParser
import logging
import optparse
import os

from . import version

try:
    from logging import NullHandler
except ImportError: # Python < 2.7
    class NullHandler(logging.Handler):
        def emit(self, record): pass

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())

RCFILE = '.pepperrc'

def get_parser():
    '''
    Return a basic optparse parser object
    '''
    parser = optparse.OptionParser(
            description=DESCRIPTION,
            usage="%prog [opts]",
            version=version.__version__)

    # TODO: add logging levels

    return parser

def get_config():
    '''
    Read a user's configuration file
    '''
    home = os.path.expanduser("~")

    f=os.path.join(home, RCFILE)
    config = ConfigParser.ConfigParser()
    config.read(f)
    return config.sections()
