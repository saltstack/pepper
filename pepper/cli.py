'''
Helper utils for using Pepper from the CLI

A central place to store repeat functionality between all the pepper scripts
(salt, salt-run, pepper, etc) such as common CLI flags (logging level).

As well as common operations such as reading/writing the auth token to a file.

'''
import json
import logging
import optparse
import os

import pepper

try:
    from logging import NullHandler
except ImportError: # Python < 2.7
    class NullHandler(logging.Handler):
        def emit(self, record): pass

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())

def get_parser():
    '''
    Return a basic optparse parser object
    '''
    parser = optparse.OptionParser(
        description=DESCRIPTION,
        usage='%prog [opts]',
        version=pepper.__version__)

    parser.add_option('-c', dest='config',
        default=os.environ.get('PEPPERRC',
            os.path.join(os.path.expanduser('~'), '.pepperrc')),
        help=textwrap.dedent('''\
            Configuration file location. Default is a file path in the
            "PEPPERRC" environment variable or ~/.pepperrc.'''))

    parser.add_option('-v', dest='verbose', default=0, action='count',
        help=textwrap.dedent('''\
            Increment output verbosity; may be specified multiple times'''))

    logger.addHandler(logging.StreamHandler())
    logger.setLevel(max(logging.ERROR - (opts.verbose * 10), 1))

    return parser

def get_config(file_path):
    '''
    Read a user's configuration file
    '''
    with open(file_path, 'rb') as f:
        config = json.load(f)

    return config
