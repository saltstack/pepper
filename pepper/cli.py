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
    from configparser import ConfigParser
except ImportError:
    # Python 2
    import ConfigParser

import pepper

try:
    from logging import NullHandler
except ImportError:  # Python < 2.7
    class NullHandler(logging.Handler):
        def emit(self, record): pass

try:
    import configparser
except ImportError:
    import ConfigParser as configparser

logging.basicConfig(format='%(levelname)s %(asctime)s %(module)s: %(message)s')
logger = logging.getLogger('pepper')
logger.addHandler(NullHandler())


class PepperCli(object):
    def __init__(self, default_timeout_in_seconds=60 * 60, seconds_to_wait=3):
        self.seconds_to_wait = seconds_to_wait
        self.parser = self.get_parser()
        self.parser.option_groups.extend([self.add_globalopts(),
            self.add_tgtopts(),
            self.add_authopts()])
        self.parser.defaults.update({'timeout': default_timeout_in_seconds,
            'fail_if_minions_dont_respond': False,
            'expr_form': 'glob'})

    def get_parser(self):
        return optparse.OptionParser(
            description=__doc__,
            usage='%prog [opts]',
            version=pepper.__version__)

    def parse(self):
        '''
        Parse all args
        '''
        self.parser.add_option('-c', dest='config',
            default=os.environ.get('PEPPERRC',
                os.path.join(os.path.expanduser('~'), '.pepperrc')),
            help=textwrap.dedent('''\
                Configuration file location. Default is a file path in the
                "PEPPERRC" environment variable or ~/.pepperrc.'''))

        self.parser.add_option('-v', dest='verbose', default=0, action='count',
            help=textwrap.dedent('''\
                Increment output verbosity; may be specified multiple times'''))

        self.parser.add_option('-H', '--debug-http', dest='debug_http', default=False,
            action='store_true', help=textwrap.dedent('''\
            Output the HTTP request/response headers on stderr'''))

        self.parser.add_option('--ignore-ssl-errors', action='store_true',
                            dest='ignore_ssl_certificate_errors',
                            default=False,
                            help=textwrap.dedent('''\
            Ignore any SSL certificate that may be encountered. Note that it is
            recommended to resolve certificate errors for production.'''))

        self.options, self.args = self.parser.parse_args()

    def add_globalopts(self):
        '''
        Misc global options
        '''
        optgroup = optparse.OptionGroup(self.parser, "Pepper ``salt`` Options",
                "Mimic the ``salt`` CLI")

        optgroup.add_option('-t', '--timeout', dest='timeout', type='int',
            help=textwrap.dedent('''\
            Specify wait time (in seconds) before returning control to the
            shell'''))

        optgroup.add_option('--client', dest='client', default='local',
            help=textwrap.dedent('''\
            specify the salt-api client to use (local, local_async,
            runner, etc)'''))

        # optgroup.add_option('--out', '--output', dest='output',
        #        help="Specify the output format for the command output")

        # optgroup.add_option('--return', default='', metavar='RETURNER',
        #    help="Redirect the output from a command to a persistent data store")

        optgroup.add_option('--fail-if-incomplete', action='store_true',
            dest='fail_if_minions_dont_respond',
            help=textwrap.dedent('''\
            Return a failure exit code if not all minions respond. This option
            requires the authenticated user have access to run the
            `jobs.list_jobs` runner function.'''))

        return optgroup

    def add_tgtopts(self):
        '''
        Targeting
        '''
        optgroup = optparse.OptionGroup(self.parser, "Targeting Options",
                "Target which minions to run commands on")

        optgroup.add_option('-E', '--pcre', dest='expr_form',
                action='store_const', const='pcre',
            help="Target hostnames using PCRE regular expressions")

        optgroup.add_option('-L', '--list', dest='expr_form',
                action='store_const', const='list',
            help="Specify a comma delimited list of hostnames")

        optgroup.add_option('-G', '--grain', dest='expr_form',
                action='store_const', const='grain',
            help="Target based on system properties")

        optgroup.add_option('--grain-pcre', dest='expr_form',
                action='store_const', const='grain_pcre',
            help="Target based on PCRE matches on system properties")

        optgroup.add_option('-R', '--range', dest='expr_form',
                action='store_const', const='range',
            help="Target based on range expression")

        optgroup.add_option('-C', '--compound', dest='expr_form',
                action='store_const', const='compound',
            help="Target based on compound expression")

        return optgroup

    def add_authopts(self):
        '''
        Authentication options
        '''
        optgroup = optparse.OptionGroup(self.parser, "Authentication Options",
                textwrap.dedent("""\
                Authentication credentials can optionally be supplied via the
                environment variables:
                SALTAPI_URL, SALTAPI_USER, SALTAPI_PASS, SALTAPI_EAUTH.
                """))

        optgroup.add_option('-u', '--saltapi-url', dest='saltapiurl',
                help="Specify the host url.  Defaults to https://localhost:8080")

        optgroup.add_option('-a', '--auth', '--eauth', '--extended-auth',
            dest='eauth', help=textwrap.dedent("""\
                    Specify the external_auth backend to authenticate against and
                    interactively prompt for credentials"""))

        optgroup.add_option('--username',
            dest='username', help=textwrap.dedent("""\
                    Optional, defaults to user name. will be prompt if empty unless --non-interactive"""))

        optgroup.add_option('--password',
            dest='password', help=textwrap.dedent("""\
                    Optional, but will be prompted unless --non-interactive"""))

        optgroup.add_option('--non-interactive',
            action='store_false', dest='interactive', help=textwrap.dedent("""\
                    Optional, fail rather than waiting for input"""), default=True)

        # optgroup.add_option('-T', '--make-token', default=False,
        #     dest='mktoken', action='store_true',
        #     help=textwrap.dedent("""\
        #         Generate and save an authentication token for re-use. The token is
        #         generated and made available for the period defined in the Salt
        #         Master."""))

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
            'SALTAPI_URL': 'https://localhost:8000/',
            'SALTAPI_USER': None,
            'SALTAPI_PASS': None,
            'SALTAPI_EAUTH': 'auto',
        }

        try:
            config = ConfigParser(interpolation=None)
        except TypeError as e:
            config = ConfigParser.RawConfigParser()
        config.read(self.options.config)

        # read file
        profile = 'main'
        if config.has_section(profile):
            for key, value in config.items(profile):
                key = key.upper()
                results[key] = config.get(profile, key)

        # get environment values
        for key, value in list(results.items()):
            results[key] = os.environ.get(key, results[key])

        # get eauth prompt options
        if self.options.saltapiurl:
            results['SALTAPI_URL'] = self.options.saltapiurl

        if results['SALTAPI_EAUTH'] == 'kerberos':
            results['SALTAPI_PASS'] = None

        if self.options.eauth:
            results['SALTAPI_EAUTH'] = self.options.eauth
        if self.options.username is None and results['SALTAPI_USER'] is None:
            if self.options.interactive:
                results['SALTAPI_USER'] = input('Username: ')
            else:
                logger.error("SALTAPI_USER required")
                raise SystemExit(1)
        else:
            if self.options.username is not None: results['SALTAPI_USER'] = self.options.username
        if self.options.password is None and results['SALTAPI_PASS'] is None:
            if self.options.interactive:
                results['SALTAPI_PASS'] = getpass.getpass(prompt='Password: ')
            else:
                logger.error("SALTAPI_PASS required")
                raise SystemExit(1)
        else:
            if self.options.password is not None: results['SALTAPI_PASS'] = self.options.password

        return results

    def parse_login(self):
        '''
        Extract the authentication credentials
        '''
        login_details = self.get_login_details()

        # Auth values placeholder; grab interactively at CLI or from config file
        url = login_details['SALTAPI_URL']
        user = login_details['SALTAPI_USER']
        passwd = login_details['SALTAPI_PASS']
        eauth = login_details['SALTAPI_EAUTH']

        return url, user, passwd, eauth

    def parse_cmd(self):
        '''
        Extract the low data for a command from the passed CLI params
        '''
        args = list(self.args)

        client = self.options.client
        low = {'client': client}

        if client.startswith('local'):
            if len(args) < 2:
                self.parser.error("Command or target not specified")

            low['expr_form'] = self.options.expr_form
            low['tgt'] = args.pop(0)
            low['fun'] = args.pop(0)
            low['arg'] = args
        elif client.startswith('runner'):
            low['fun'] = args.pop(0)
            for arg in args:
                key, value = arg.split('=', 1)
                low[key] = value
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
        async_ret = api.low(load)
        jid = async_ret['return'][0]['jid']
        nodes = async_ret['return'][0]['minions']

        # keep trying until all expected nodes return
        total_time = self.seconds_to_wait
        ret = {}
        exit_code = 0
        while True:
            if total_time > self.options.timeout:
                break

            jid_ret = api.lookup_jid(jid)
            ret_nodes = list(jid_ret['return'][0].keys())

            if set(ret_nodes) == set(nodes):
                ret = jid_ret
                exit_code = 0
                break
            else:
                exit_code = 1
                time.sleep(self.seconds_to_wait)
                continue

        exit_code = exit_code if self.options.fail_if_minions_dont_respond else 0
        return exit_code, ret

    def run(self):
        '''
        Parse all arguments and call salt-api
        '''
        self.parse()

        # move logger instantiation to method?
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(max(logging.ERROR - (self.options.verbose * 10), 1))

        load = self.parse_cmd()
        creds = iter(self.parse_login())

        api = pepper.Pepper(next(creds), debug_http=self.options.debug_http, ignore_ssl_errors=self.options.ignore_ssl_certificate_errors)
        auth = api.login(*list(creds))

        if self.options.fail_if_minions_dont_respond:
            exit_code, ret = self.poll_for_returns(api, load)
        else:
            ret = api.low(load)
            exit_code = 0

        return (exit_code, json.dumps(ret, sort_keys=True, indent=4))
