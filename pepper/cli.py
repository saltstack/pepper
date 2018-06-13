'''
A CLI interface to a remote salt-api instance

'''
from __future__ import print_function
import json
import logging
import optparse
import os
import textwrap
import getpass
import time
try:
    # Python 3
    from configparser import ConfigParser, RawConfigParser
except ImportError:
    # Python 2
    from ConfigParser import ConfigParser, RawConfigParser

try:
    input = raw_input
except NameError:
    pass

import pepper

try:
    from logging import NullHandler
except ImportError:  # Python < 2.7
    class NullHandler(logging.Handler):
        def emit(self, record): pass

logging.basicConfig(format='%(levelname)s %(asctime)s %(module)s: %(message)s')
logger = logging.getLogger('pepper')
logger.addHandler(NullHandler())


class PepperCli(object):
    def __init__(self, seconds_to_wait=3):
        self.seconds_to_wait = seconds_to_wait
        self.parser = self.get_parser()
        self.parser.option_groups.extend([
            self.add_globalopts(),
            self.add_tgtopts(),
            self.add_authopts()
        ])
        self.parse()

    def get_parser(self):
        return optparse.OptionParser(
            description=__doc__,
            usage='%prog [opts]',
            version=pepper.__version__)

    def parse(self):
        '''
        Parse all args
        '''
        self.parser.add_option(
            '-c', dest='config',
            default=os.environ.get(
                'PEPPERRC',
                os.path.join(os.path.expanduser('~'), '.pepperrc')
            ),
            help=textwrap.dedent('''
                Configuration file location. Default is a file path in the
                "PEPPERRC" environment variable or ~/.pepperrc.
            '''),
        )

        self.parser.add_option(
            '-p', dest='profile',
            default=os.environ.get('PEPPERPROFILE', 'main'),
            help=textwrap.dedent('''
                Profile in config file to use. Default is "PEPPERPROFILE" environment
                variable or 'main'
            '''),
        )

        self.parser.add_option(
            '-m', dest='master',
            default=os.environ.get(
                'MASTER_CONFIG',
                os.path.join(os.path.expanduser('~'), '.config', 'pepper', 'master')
            ),
            help=textwrap.dedent('''
                Master Configuration file location for configuring outputters.
                default: ~/.config/pepper/master
            '''),
        )

        self.parser.add_option(
            '-o', '--out', dest='output', default=None,
            help=textwrap.dedent('''
                Salt outputter to use for printing out returns.
            ''')
        )

        self.parser.add_option(
            '-v', dest='verbose', default=0, action='count',
            help=textwrap.dedent('''
                Increment output verbosity; may be specified multiple times
            '''),
        )

        self.parser.add_option(
            '-H', '--debug-http', dest='debug_http', default=False, action='store_true',
            help=textwrap.dedent('''
                Output the HTTP request/response headers on stderr
            '''),
        )

        self.parser.add_option(
            '--ignore-ssl-errors', action='store_true', dest='ignore_ssl_certificate_errors', default=False,
            help=textwrap.dedent('''
                Ignore any SSL certificate that may be encountered. Note that it is
                recommended to resolve certificate errors for production.
            '''),
        )

        self.options, self.args = self.parser.parse_args()

    def add_globalopts(self):
        '''
        Misc global options
        '''
        optgroup = optparse.OptionGroup(self.parser, "Pepper ``salt`` Options", "Mimic the ``salt`` CLI")

        optgroup.add_option(
            '-t', '--timeout', dest='timeout', type='int', default=60,
            help=textwrap.dedent('''
                Specify wait time (in seconds) before returning control to the shell
            '''),
        )

        optgroup.add_option(
            '--client', dest='client', default='local',
            help=textwrap.dedent('''
                specify the salt-api client to use (local, local_async,
                runner, etc)
            '''),
        )

        optgroup.add_option(
            '--json', dest='json_input',
            help=textwrap.dedent('''
                Enter JSON at the CLI instead of positional (text) arguments. This
                is useful for arguments that need complex data structures.
                Specifying this argument will cause positional arguments to be
                ignored.
            '''),
        )

        optgroup.add_option(
            '--json-file', dest='json_file',
            help=textwrap.dedent('''
                Specify file containing the JSON to be used by pepper
            '''),
        )

        optgroup.add_option(
            '--fail-if-incomplete', action='store_true', dest='fail_if_minions_dont_respond', default=False,
            help=textwrap.dedent('''
                Return a failure exit code if not all minions respond. This option
                requires the authenticated user have access to run the
                `jobs.list_jobs` runner function.
            '''),
        )

        return optgroup

    def add_tgtopts(self):
        '''
        Targeting
        '''
        optgroup = optparse.OptionGroup(self.parser, "Targeting Options", "Target which minions to run commands on")

        optgroup.defaults.update({'expr_form': 'glob'})

        optgroup.add_option(
            '-E', '--pcre', dest='expr_form', action='store_const', const='pcre',
            help="Target hostnames using PCRE regular expressions",
        )

        optgroup.add_option(
            '-L', '--list', dest='expr_form', action='store_const', const='list',
            help="Specify a comma delimited list of hostnames",
        )

        optgroup.add_option(
            '-G', '--grain', dest='expr_form', action='store_const', const='grain',
            help="Target based on system properties",
        )

        optgroup.add_option(
            '--grain-pcre', dest='expr_form', action='store_const', const='grain_pcre',
            help="Target based on PCRE matches on system properties",
        )

        optgroup.add_option(
            '-I', '--pillar', dest='expr_form', action='store_const', const='pillar',
            help="Target based on pillar values",
        )

        optgroup.add_option(
            '--pillar-pcre', dest='expr_form', action='store_const', const='pillar_pcre',
            help="Target based on PCRE matches on pillar values"
        )

        optgroup.add_option(
            '-R', '--range', dest='expr_form', action='store_const', const='range',
            help="Target based on range expression",
        )

        optgroup.add_option(
            '-C', '--compound', dest='expr_form', action='store_const', const='compound',
            help="Target based on compound expression",
        )

        optgroup.add_option(
            '-N', '--nodegroup', dest='expr_form', action='store_const', const='nodegroup',
            help="Target based on a named nodegroup",
        )

        optgroup.add_option('--batch', dest='batch', default=None)

        return optgroup

    def add_authopts(self):
        '''
        Authentication options
        '''
        optgroup = optparse.OptionGroup(
            self.parser, "Authentication Options",
            textwrap.dedent('''
                Authentication credentials can optionally be supplied via the
                environment variables:
                SALTAPI_URL, SALTAPI_USER, SALTAPI_PASS, SALTAPI_EAUTH.
            '''),
        )

        optgroup.add_option(
            '-u', '--saltapi-url', dest='saltapiurl',
            help="Specify the host url.  Defaults to https://localhost:8080"
        )

        optgroup.add_option(
            '-a', '--auth', '--eauth', '--extended-auth', dest='eauth',
            help=textwrap.dedent('''
                Specify the external_auth backend to authenticate against and
                interactively prompt for credentials
            '''),
        )

        optgroup.add_option(
            '--username', dest='username',
            help=textwrap.dedent('''
                Optional, defaults to user name. will be prompt if empty unless --non-interactive
            '''),
        )

        optgroup.add_option(
            '--password', dest='password',
            help=textwrap.dedent('''
                Optional, but will be prompted unless --non-interactive
            '''),
        )

        optgroup.add_option(
            '--token-expire', dest='token_expire',
            help=textwrap.dedent('''
                Set eauth token expiry in seconds. Must be allowed per
                user. See the `token_expire_user_override` Master setting
                for more info.
            '''),
        )

        optgroup.add_option(
            '--non-interactive', action='store_false', dest='interactive', default=True,
            help=textwrap.dedent('''
                Optional, fail rather than waiting for input
            ''')
        )

        optgroup.add_option(
            '-T', '--make-token', default=False, dest='mktoken', action='store_true',
            help=textwrap.dedent('''
                Generate and save an authentication token for re-use. The token is
                generated and made available for the period defined in the Salt
                Master.
            '''),
        )

        optgroup.add_option(
            '-r', '--run-uri', default=False, dest='userun', action='store_true',
            help=textwrap.dedent('''
                Use an eauth token from /token and send commands through the
                /run URL instead of the traditional session token
                approach.
            '''),
        )

        optgroup.add_option(
            '-x', dest='cache',
            default=os.environ.get(
                'PEPPERCACHE',
                os.path.join(os.path.expanduser('~'), '.peppercache')
            ),
            help=textwrap.dedent('''
                Cache file location. Default is a file path in the
                "PEPPERCACHE" environment variable or ~/.peppercache.
            '''),
        )

        return optgroup

    def get_login_details(self):
        '''
        This parses the config file, environment variables and command line options
        and returns the config values
        Order of parsing:
            command line options, ~/.pepperrc, environment, defaults
        '''

        # setting default values
        results = {
            'SALTAPI_USER': None,
            'SALTAPI_PASS': None,
            'SALTAPI_EAUTH': 'auto',
        }

        try:
            config = ConfigParser(interpolation=None)
        except TypeError:
            config = RawConfigParser()
        config.read(self.options.config)

        # read file
        profile = self.options.profile
        if config.has_section(profile):
            for key, value in list(results.items()):
                if config.has_option(profile, key):
                    results[key] = config.get(profile, key)

        # get environment values
        for key, value in list(results.items()):
            results[key] = os.environ.get(key, results[key])

        if results['SALTAPI_EAUTH'] == 'kerberos':
            results['SALTAPI_PASS'] = None

        if self.options.eauth:
            results['SALTAPI_EAUTH'] = self.options.eauth
        if self.options.token_expire:
            results['SALTAPI_TOKEN_EXPIRE'] = self.options.token_expire
        if self.options.username is None and results['SALTAPI_USER'] is None:
            if self.options.interactive:
                results['SALTAPI_USER'] = input('Username: ')
            else:
                logger.error("SALTAPI_USER required")
                raise SystemExit(1)
        else:
            if self.options.username is not None:
                results['SALTAPI_USER'] = self.options.username
        if self.options.password is None and results['SALTAPI_PASS'] is None:
            if self.options.interactive:
                results['SALTAPI_PASS'] = getpass.getpass(prompt='Password: ')
            else:
                logger.error("SALTAPI_PASS required")
                raise SystemExit(1)
        else:
            if self.options.password is not None:
                results['SALTAPI_PASS'] = self.options.password

        return results

    def parse_url(self):
        '''
        Determine api url
        '''
        url = 'https://localhost:8000/'

        try:
            config = ConfigParser(interpolation=None)
        except TypeError:
            config = RawConfigParser()
        config.read(self.options.config)

        # read file
        profile = self.options.profile
        if config.has_section(profile):
            if config.has_option(profile, "SALTAPI_URL"):
                url = config.get(profile, "SALTAPI_URL")

        # get environment values
        url = os.environ.get("SALTAPI_URL", url)

        # get eauth prompt options
        if self.options.saltapiurl:
            url = self.options.saltapiurl

        return url

    def parse_login(self):
        '''
        Extract the authentication credentials
        '''
        login_details = self.get_login_details()

        # Auth values placeholder; grab interactively at CLI or from config
        username = login_details['SALTAPI_USER']
        password = login_details['SALTAPI_PASS']
        eauth = login_details['SALTAPI_EAUTH']

        ret = dict(username=username, password=password, eauth=eauth)

        token_expire = login_details.get('SALTAPI_TOKEN_EXPIRE', None)
        if token_expire:
            ret['token_expire'] = int(token_expire)

        return ret

    def parse_cmd(self):
        '''
        Extract the low data for a command from the passed CLI params
        '''
        # Short-circuit if JSON was given.
        if self.options.json_input:
            try:
                return json.loads(self.options.json_input)
            except ValueError:
                logger.error("Invalid JSON given.")
                raise SystemExit(1)

        if self.options.json_file:
            try:
                with open(self.options.json_file, 'r') as json_content:
                    try:
                        return json.load(json_content)
                    except ValueError:
                        logger.error("Invalid JSON given.")
                        raise SystemExit(1)
            except Exception as e:
                logger.error(
                    'Cannot open file: {0}, {1}'.format(
                        self.options.json_file, repr(e)
                    )
                )
                raise SystemExit(1)

        args = list(self.args)

        client = self.options.client if not self.options.batch else 'local_batch'
        low = {'client': client}

        if client.startswith('local'):
            if len(args) < 2:
                self.parser.error("Command or target not specified")

            low['tgt_type'] = self.options.expr_form
            low['tgt'] = args.pop(0)
            low['fun'] = args.pop(0)
            low['batch'] = self.options.batch
            low['arg'] = args
            low['full_return'] = True
        elif client.startswith('runner'):
            low['fun'] = args.pop(0)
            for arg in args:
                if '=' in arg:
                    key, value = arg.split('=', 1)
                    low[key] = value
                else:
                    low.setdefault('args', []).append(arg)
        elif client.startswith('wheel'):
            low['fun'] = args.pop(0)
            for arg in args:
                if '=' in arg:
                    key, value = arg.split('=', 1)
                    low[key] = value
                else:
                    low.setdefault('args', []).append(arg)
        elif client.startswith('ssh'):
            if len(args) < 2:
                self.parser.error("Command or target not specified")

            low['tgt_type'] = self.options.expr_form
            low['tgt'] = args.pop(0)
            low['fun'] = args.pop(0)
            low['batch'] = self.options.batch
            low['arg'] = args
        else:
            if len(args) < 1:
                self.parser.error("Command not specified")

            low['fun'] = args.pop(0)
            low['arg'] = args

        return [low]

    def poll_for_returns(self, api, load):
        '''
        Run a command with the local_async client and periodically poll the job
        cache for returns for the job.
        '''
        load[0]['client'] = 'local_async'
        async_ret = self.low(api, load)
        jid = async_ret['return'][0]['jid']
        nodes = async_ret['return'][0]['minions']
        ret_nodes = []
        exit_code = 1

        # keep trying until all expected nodes return
        total_time = 0
        start_time = time.time()
        exit_code = 0
        while True:
            total_time = time.time() - start_time
            if total_time > self.options.timeout:
                exit_code = 1
                break

            jid_ret = self.low(api, [{
                'client': 'runner',
                'fun': 'jobs.lookup_jid',
                'kwarg': {
                    'jid': jid,
                },
            }])

            responded = set(jid_ret['return'][0].keys()) ^ set(ret_nodes)
            for node in responded:
                yield None, "{{{}: {}}}".format(
                    node,
                    jid_ret['return'][0][node])
            ret_nodes = list(jid_ret['return'][0].keys())

            if set(ret_nodes) == set(nodes):
                exit_code = 0
                break
            else:
                time.sleep(self.seconds_to_wait)

        exit_code = exit_code if self.options.fail_if_minions_dont_respond else 0
        yield exit_code, "{{Failed: {}}}".format(
            list(set(ret_nodes) ^ set(nodes)))

    def login(self, api):
        login = api.token if self.options.userun else api.login

        if self.options.mktoken:
            token_file = self.options.cache
            try:
                with open(token_file, 'rt') as f:
                    auth = json.load(f)
                if auth['expire'] < time.time()+30:
                    logger.error('Login token expired')
                    raise Exception('Login token expired')
            except Exception as e:
                if e.args[0] is not 2:
                    logger.error('Unable to load login token from {0} {1}'.format(token_file, str(e)))
                    if os.path.isfile(token_file):
                        os.remove(token_file)
                auth = login(**self.parse_login())
                try:
                    oldumask = os.umask(0)
                    fdsc = os.open(token_file, os.O_WRONLY | os.O_CREAT, 0o600)
                    with os.fdopen(fdsc, 'w+t') as f:
                        json.dump(auth, f)
                except Exception as e:
                    logger.error('Unable to save token to {0} {1}'.format(token_file, str(e)))
                finally:
                    os.umask(oldumask)
        else:
            auth = login(**self.parse_login())

        api.auth = auth
        self.auth = auth
        return auth

    def low(self, api, load):
        path = '/run' if self.options.userun else '/'

        if self.options.userun:
            for i in load:
                i['token'] = self.auth['token']

        return api.low(load, path=path)

    def run(self):
        '''
        Parse all arguments and call salt-api
        '''
        # move logger instantiation to method?
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(max(logging.ERROR - (self.options.verbose * 10), 1))

        load = self.parse_cmd()

        api = pepper.Pepper(
            self.parse_url(),
            debug_http=self.options.debug_http,
            ignore_ssl_errors=self.options.ignore_ssl_certificate_errors)

        self.login(api)

        if self.options.fail_if_minions_dont_respond:
            for exit_code, ret in self.poll_for_returns(api, load):
                yield exit_code, json.dumps(ret, sort_keys=True, indent=4)
        else:
            exit_code = 0
            # keep trying until all expected nodes return
            total_time = 0
            start_time = time.time()
            while True:
                total_time = time.time() - start_time
                if total_time > self.options.timeout:
                    exit_code = 1
                    break
                try:
                    ret = self.low(api, load)
                    if all(ret["return"][0].values()):
                        break
                    logger.debug('Incorrect reply %s', ret)
                except Exception:
                    logger.debug('Error with self.low(api, load) request', exc_info=True)
                time.sleep(self.seconds_to_wait)
            yield exit_code, json.dumps(ret, sort_keys=True, indent=4)
