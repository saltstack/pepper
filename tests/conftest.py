# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

# Import python libraries
import itertools
import os.path
import shutil
import subprocess
import sys
import tempfile
import yaml

# Import pytest libraries
import pytest
from pytestsalt.utils import SaltDaemonScriptBase, start_daemon, get_unused_localhost_port

# Import Pepper libraries
import pepper

DEFAULT_MASTER_ID = 'pytest-salt-master'
DEFAULT_MINION_ID = 'pytest-salt-minion'


class SaltApi(SaltDaemonScriptBase):
    '''
    Class which runs the salt-api daemon
    '''

    def get_script_args(self):
        return ['-l', 'quiet']

    def get_check_events(self):
        if sys.platform.startswith('win'):
            return super(SaltApi, self).get_check_events()
        return set(['salt/{0}/{1}/start'.format(self.config['__role'], self.config['id'])])

    def get_check_ports(self):
        return [self.config['rest_cherrypy']['port']]


@pytest.fixture(scope='session')
def salt_api_port():
    '''
    Returns an unused localhost port for the api port
    '''
    return get_unused_localhost_port()


@pytest.fixture
def pepper_client(session_salt_api, salt_api_port):
    client = pepper.Pepper('http://localhost:{0}'.format(salt_api_port))
    client.login('pepper', 'pepper', 'sharedsecret')
    return client


@pytest.fixture
def tokfile():
    tokdir = tempfile.mkdtemp()
    yield os.path.join(tokdir, 'peppertok.json')
    shutil.rmtree(tokdir)


@pytest.fixture
def pepper_cli(session_salt_api, salt_api_port):
    '''
    Wrapper to invoke Pepper with common params and inside an empty env
    '''
    def_args = [
        'pepper',
        '--saltapi-url=http://localhost:{0}'.format(salt_api_port),
        '--username={0}'.format('pepper'),
        '--password={0}'.format('pepper'),
        '--eauth={0}'.format('sharedsecret'),
        '--out=json',
    ]

    def _run_pepper_cli(*args):
        result = subprocess.check_output(itertools.chain(def_args, args))
        try:
            return yaml.load(result)
        except yaml.parser.ParserError:
            return [yaml.load(ret.strip(b'"')) for ret in result.strip(b'\n').split(b'\n')]
    return _run_pepper_cli


@pytest.fixture(scope='session')
def session_master_config_overrides(salt_api_port):
    return {
        'rest_cherrypy': {
            'port': salt_api_port,
            'disable_ssl': True,
        },
        'external_auth': {
            'sharedsecret': {
                'pepper': [
                    '.*',
                    '@jobs',
                    '@wheel',
                    '@runner',
                ],
            },
        },
        'sharedsecret': 'pepper',
    }


@pytest.fixture(scope='session')
def session_api_log_prefix(master_id):
    return 'salt-api/{0}'.format(master_id)


@pytest.fixture(scope='session')
def cli_api_script_name():
    '''
    Return the CLI script basename
    '''
    return 'salt-api'


@pytest.yield_fixture(scope='session')
def session_salt_api_before_start():
    '''
    This fixture should be overridden if you need to do
    some preparation and clean up work before starting
    the salt-api and after ending it.
    '''
    # Prep routines go here

    # Start the salt-api
    yield

    # Clean routines go here


@pytest.yield_fixture(scope='session')
def session_salt_api_after_start(session_salt_api):
    '''
    This fixture should be overridden if you need to do
    some preparation and clean up work after starting
    the salt-api and before ending it.
    '''
    # Prep routines go here

    # Resume test execution
    yield

    # Clean routines go here


@pytest.fixture(scope='session')
def _salt_fail_hard(request, salt_fail_hard):
    '''
    Return the salt fail hard value
    '''
    fail_hard = request.config.getoption('salt_fail_hard')
    if fail_hard is not None:
        # We were passed --salt-fail-hard as a CLI option
        return fail_hard

    # The salt fail hard was not passed as a CLI option
    fail_hard = request.config.getini('salt_fail_hard')
    if fail_hard != []:
        # We were passed salt_fail_hard as a INI option
        return fail_hard

    return salt_fail_hard


@pytest.fixture(scope='session')
def master_id(salt_master_id_counter):
    '''
    Returns the master id
    '''
    return DEFAULT_MASTER_ID + '-{0}'.format(salt_master_id_counter())


@pytest.fixture(scope='session')
def minion_id(salt_minion_id_counter):
    '''
    Returns the minion id
    '''
    return DEFAULT_MINION_ID + '-{0}'.format(salt_minion_id_counter())


@pytest.fixture(scope='session')
def session_salt_api(request,
                     session_salt_minion,
                     session_master_id,
                     session_master_config,
                     session_salt_api_before_start,  # pylint: disable=unused-argument
                     session_api_log_prefix,
                     cli_api_script_name,
                     log_server,
                     _cli_bin_dir,
                     session_conf_dir):
    '''
    Returns a running salt-api
    '''
    return start_daemon(request,
                        daemon_name='salt-api',
                        daemon_id=session_master_id,
                        daemon_log_prefix=session_api_log_prefix,
                        daemon_cli_script_name=cli_api_script_name,
                        daemon_config=session_master_config,
                        daemon_config_dir=session_conf_dir,
                        daemon_class=SaltApi,
                        bin_dir_path=_cli_bin_dir,
                        start_timeout=30)
