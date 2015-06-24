'''
A CLI interface to a remote salt-api instance

'''
from __future__ import print_function

import json
import logging
import optparse
import os
import textwrap
import ConfigParser
import getpass
import time

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
    def __init__(self, default_timeout_in_seconds=60*60, seconds_to_wait=3):
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

        self.options, self.args = self.parser.parse_args()

    def add_globalopts(self):
        '''
        Misc global options
        '''
        optgroup = optparse.OptionGroup(self.parser, "Pepper ``salt`` Options",
                "Mimic the ``salt`` CLI")

        optgroup.add_option('-t', '--timeout', dest='timeout', type ='int',
            help="Specify wait time (in seconds) before returning control to the shell")

        # optgroup.add_option('--out', '--output', dest='output',
        #        help="Specify the output format for the command output")

        # optgroup.add_option('--return', default='', metavar='RETURNER',
        #    help="Redirect the output from a command to a persistent data store")

        optgroup.add_option('--fail-if-incomplete', action='store_true',
            dest='fail_if_minions_dont_respond',
            help="Optional, return a failure exit code if not all minions respond")

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
            'SALTAPI_USER': 'saltdev',
            'SALTAPI_PASS': 'saltdev',
            'SALTAPI_EAUTH': 'auto',
        }

        config = ConfigParser.RawConfigParser()
        config.read(self.options.config)

        # read file
        profile = 'main'
        if config.has_section(profile):
            for key, value in config.items(profile):
                key = key.upper()
                results[key] = config.get(profile, key)

        # get environment values
        for key, value in results.items():
            results[key] = os.environ.get(key, results[key])

        # get eauth prompt options
        if self.options.saltapiurl:
            results['SALTAPI_URL'] = self.options.saltapiurl

        if results['SALTAPI_EAUTH'] == 'kerberos':
            results['SALTAPI_PASS'] = None

        if self.options.eauth:
            results['SALTAPI_EAUTH'] = self.options.eauth
            if self.options.username is None:
                if self.options.interactive:
                    results['SALTAPI_USER'] = raw_input('Username: ')
                else:
                    logger.error("SALTAPI_USER required")
                    raise SystemExit(1)
            else:
                results['SALTAPI_USER'] = self.options.username
            if self.options.password is None:
                if self.options.interactive:
                    results['SALTAPI_PASS'] = getpass.getpass(prompt='Password: ')
                else:
                    logger.error("SALTAPI_PASS required")
                    raise SystemExit(1)
            else:
                results['SALTAPI_PASS'] = self.options.password

        return results

    def run(self):
        '''
        Parse all arguments and call salt-api
        '''
        self.parse()

        # move logger instantiation to method?
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(max(logging.ERROR - (self.options.verbose * 10), 1))

        if len(self.args) < 2:
            self.parser.error("Command not specified")

        tgt, fun = self.args[0:2]

        login_details = self.get_login_details()

        # Auth values placeholder; grab interactively at CLI or from config file
        salturl = login_details['SALTAPI_URL']
        saltuser = login_details['SALTAPI_USER']
        saltpass = login_details['SALTAPI_PASS']
        salteauth = login_details['SALTAPI_EAUTH']

        api = pepper.Pepper(salturl, debug_http=self.options.debug_http)
        auth = api.login(saltuser, saltpass, salteauth)
        nodesJidRet = api.local_async(tgt=tgt, fun='test.ping', expr_form=self.options.expr_form)
        nodesJid = nodesJidRet['return'][0]['jid']
        time.sleep(self.seconds_to_wait)
        nodesRet = api.lookup_jid(nodesJid)

        if fun == 'test.ping':
            return (0,json.dumps(nodesRet['return'][0], sort_keys=True, indent=4))

        nodes = nodesRet['return'][0].keys()
        if nodes == []:
            return (0,json.dumps({}))

        commandJidRet = api.local_async(tgt=nodes, fun=fun, arg=self.args[2:], expr_form='list')
        commandJid = commandJidRet['return'][0]['jid']
        # keep trying until all expected nodes return
        commandRet = api.lookup_jid(commandJid)
        returnedNodes = commandRet['return'][0].keys()
        total_time = self.seconds_to_wait

        while set(returnedNodes) != set(nodes):
            if total_time > self.options.timeout :
                break

            time.sleep(self.seconds_to_wait)
            commandRet = api.lookup_jid(commandJid)
            returnedNodes = commandRet['return'][0].keys()

        if set(returnedNodes) != set(nodes) and self.options.fail_if_minions_dont_respond is True:
            exit_code = 1
        else:
            exit_code = 0

        return (exit_code,json.dumps(commandRet['return'][0], sort_keys=True, indent=4))
