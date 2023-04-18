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
from pytestskipmarkers.utils import ports
from saltfactories.utils import random_string, running_username

# Import Pepper libraries
import pepper
import pepper.script


log = logging.getLogger(__name__)


@pytest.fixture(scope='session')
def sshd_config_dir(salt_factories):
    config_dir = salt_factories.get_root_dir_for_daemon("sshd")
    yield config_dir
    shutil.rmtree(str(config_dir), ignore_errors=True)


@pytest.fixture(scope='session')
def session_sshd_server(salt_factories, sshd_config_dir, session_master):
    sshd_config_dict = {
        "Protocol": "2",
        # Turn strict modes off so that we can operate in /tmp
        "StrictModes": "no",
        # Logging
        "SyslogFacility": "AUTH",
        "LogLevel": "INFO",
        # Authentication:
        "LoginGraceTime": "120",
        "PermitRootLogin": "without-password",
        "PubkeyAuthentication": "yes",
        # Don't read the user's ~/.rhosts and ~/.shosts files
        "IgnoreRhosts": "yes",
        "HostbasedAuthentication": "no",
        # To enable empty passwords, change to yes (NOT RECOMMENDED)
        "PermitEmptyPasswords": "no",
        # Change to yes to enable challenge-response passwords (beware issues with
        # some PAM modules and threads)
        "ChallengeResponseAuthentication": "no",
        # Change to no to disable tunnelled clear text passwords
        "PasswordAuthentication": "no",
        "X11Forwarding": "no",
        "X11DisplayOffset": "10",
        "PrintMotd": "no",
        "PrintLastLog": "yes",
        "TCPKeepAlive": "yes",
        "AcceptEnv": "LANG LC_*",
        "UsePAM": "yes",
    }
    factory = salt_factories.get_sshd_daemon(
        sshd_config_dict=sshd_config_dict,
        config_dir=sshd_config_dir,
    )
    with factory.started():
        yield factory


@pytest.fixture(scope='session')
def session_ssh_roster_config(session_sshd_server, session_master):
    roster_contents = """
    localhost:
      host: 127.0.0.1
      port: {}
      user: {}
      priv: {}
      mine_functions:
        test.arg: ['itworked']
    """.format(
        session_sshd_server.listen_port,
        running_username(),
        session_sshd_server.client_key
    )
    with pytest.helpers.temp_file(
        "roster", roster_contents, session_master.config_dir
    ) as roster_file:
        yield roster_file


@pytest.fixture(scope='session')
def salt_api_port():
    '''
    Returns an unused localhost port for the api port
    '''
    return ports.get_unused_localhost_port()


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
def session_master_factory(request, salt_factories, session_master_config_overrides):
    return salt_factories.salt_master_daemon(
        random_string("master-"),
        overrides=session_master_config_overrides
    )


@pytest.fixture(scope='session')
def session_master(session_master_factory):
    with session_master_factory.started():
        yield session_master_factory


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
def session_minion_factory(session_master_factory):
    """Return a factory for a randomly named minion connected to master."""
    minion_factory = session_master_factory.salt_minion_daemon(random_string("minion-"))
    minion_factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, session_master_factory, minion_factory.id
    )
    return minion_factory


@pytest.fixture(scope='session')
def session_minion(session_master, session_minion_factory):  # noqa
    assert session_master.is_running()
    with session_minion_factory.started():
        yield session_minion_factory


@pytest.fixture(scope='session')
def session_minion_id(session_minion):
    return session_minion.id


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
def session_salt_api_factory(session_master_factory):
    return session_master_factory.salt_api_daemon()


@pytest.fixture(scope='session')
def session_salt_api(session_master, session_salt_api_factory):
    assert session_master.is_running()
    with session_salt_api_factory.started():
        yield session_salt_api_factory


def pytest_addoption(parser):
    parser.addoption(
         '--salt-api-backend',
         action='store',
         default='rest_cherrypy',
         help='which backend to use for salt-api, must be one of rest_cherrypy or rest_tornado',
     )
