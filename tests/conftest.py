# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals, print_function

# Import python libraries
import logging
import os.path
import shutil
import sys
import tempfile
import textwrap

# Import Salt Libraries
import salt.utils.yaml as yaml

# Import pytest libraries
import pytest
from pytestsalt.utils import SaltDaemonScriptBase, start_daemon, get_unused_localhost_port

# Import Pepper libraries
import pepper
import pepper.script

DEFAULT_MASTER_ID = 'pytest-salt-master'
DEFAULT_MINION_ID = 'pytest-salt-minion'

log = logging.getLogger(__name__)


class SaltApi(SaltDaemonScriptBase):
    '''
    Class which runs the salt-api daemon
    '''

    def get_script_args(self):
        return ['-l', 'quiet']

    def get_check_ports(self):
        if 'rest_cherrypy' in self.config:
            return [self.config['rest_cherrypy']['port']]

        if 'rest_tornado' in self.config:
            return [self.config['rest_tornado']['port']]


@pytest.fixture(scope='session')
def salt_api_port():
    '''
    Returns an unused localhost port for the api port
    '''
    return get_unused_localhost_port()


@pytest.fixture(scope='session')
def pepperconfig(salt_api_port):
    config = textwrap.dedent('''
        [main]
        SALTAPI_URL=http://localhost:{0}/
        SALTAPI_USER=pepper
        SALTAPI_PASS=pepper
        SALTAPI_EAUTH=sharedsecret
        [pepper]
        SALTAPI_URL=http://localhost:{0}/
        SALTAPI_USER=pepper
        SALTAPI_PASS=pepper
        SALTAPI_EAUTH=sharedsecret
        [baduser]
        SALTAPI_URL=http://localhost:{0}/
        SALTAPI_USER=saltdev
        SALTAPI_PASS=saltdev
        SALTAPI_EAUTH=pam
        [badapi]
        SALTAPI_URL=git://localhost:{0}/
        [noapi]
        SALTAPI_USER=pepper
        SALTAPI_PASS=pepper
        SALTAPI_EAUTH=sharedsecret
        [noopts]
        SALTAPI_URL=http://localhost:{0}/
        SALTAPI_EAUTH=kerberos
    '''.format(salt_api_port))
    with open('tests/.pepperrc', 'w') as pepper_file:
        print(config, file=pepper_file)
    yield
    os.remove('tests/.pepperrc')


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
def output_file():
    '''
    Returns the path to the salt master configuration file
    '''
    out_dir = tempfile.mkdtemp()
    yield os.path.join(out_dir, 'output')
    shutil.rmtree(out_dir)


@pytest.fixture(params=['/run', '/login'])
def pepper_cli(request, session_salt_api, salt_api_port, output_file, session_sshd_server):
    '''
    Wrapper to invoke Pepper with common params and inside an empty env
    '''
    if request.config.getoption('--salt-api-backend') == 'rest_tornado' and request.param == '/run':
        pytest.xfail("rest_tornado does not support /run endpoint until next release")

    def_args = [
        '--out=json',
        '--output-file={0}'.format(output_file),
        '-c', 'tests/.pepperrc',
    ]

    if request.param == '/run':
        def_args = ['--run-uri'] + def_args

    def _run_pepper_cli(*args, **kwargs):
        sys.argv = ['pepper', '-p', kwargs.pop('profile', 'main')] + def_args + list(args)
        exitcode = pepper.script.Pepper()()
        try:
            with open(output_file, 'r') as result:
                try:
                    return yaml.load(result)
                except yaml.parser.ParserError:
                    result.seek(0)
                    return [yaml.load('{0}}}'.format(ret).strip('"')) for ret in result.read().split('}"\n') if ret]
        except Exception as exc:
            log.error('ExitCode %s: %s', exitcode, exc)
            return exitcode

    return _run_pepper_cli

@pytest.fixture(scope='session')
def session_master_config_overrides(request, salt_api_port, salt_api_backend):
    return {
        salt_api_backend: {
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
        'token_expire': 94670856,
        'ignore_host_keys': True,
        'ssh_wipe': True,
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
def salt_api_backend(request):
    '''
    Return the salt-api backend (cherrypy or tornado)
    '''
    backend = request.config.getoption('--salt-api-backend')
    if backend is not None:
        return backend

    backend = request.config.getini('salt_api_backend')
    if backend is not None:
        return backend

    return 'rest_cherrypy'


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


@pytest.fixture(scope='session')
def session_sshd_config_lines(session_sshd_port):
    '''
    Return a list of lines which will make the sshd_config file
    '''
    return [
        'Port {0}'.format(session_sshd_port),
        'ListenAddress 127.0.0.1',
        'Protocol 2',
        'UsePrivilegeSeparation yes',
        '# Turn strict modes off so that we can operate in /tmp',
        'StrictModes no',
        '# Logging',
        'SyslogFacility AUTH',
        'LogLevel INFO',
        '# Authentication:',
        'LoginGraceTime 120',
        'PermitRootLogin without-password',
        'StrictModes yes',
        'PubkeyAuthentication yes',
        '#AuthorizedKeysFile	%h/.ssh/authorized_keys',
        '#AuthorizedKeysFile	key_test.pub',
        '# Don\'t read the user\'s ~/.rhosts and ~/.shosts files',
        'IgnoreRhosts yes',
        '# similar for protocol version 2',
        'HostbasedAuthentication no',
        '#IgnoreUserKnownHosts yes',
        '# To enable empty passwords, change to yes (NOT RECOMMENDED)',
        'PermitEmptyPasswords no',
        '# Change to yes to enable challenge-response passwords (beware issues with',
        '# some PAM modules and threads)',
        'ChallengeResponseAuthentication no',
        '# Change to no to disable tunnelled clear text passwords',
        'PasswordAuthentication no',
        'X11Forwarding no',
        'X11DisplayOffset 10',
        'PrintMotd no',
        'PrintLastLog yes',
        'TCPKeepAlive yes',
        '#UseLogin no',
        'AcceptEnv LANG LC_*',
        'Subsystem sftp /usr/lib/openssh/sftp-server',
        '#UsePAM yes',
    ]


def pytest_addoption(parser):
    parser.addoption(
         '--salt-api-backend',
         action='store',
         default='rest_cherrypy',
         help='which backend to use for salt-api, must be one of rest_cherrypy or rest_tornado',
     )
