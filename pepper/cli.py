'''
A CLI interface to a remote salt-api instance

'''
from __future__ import print_function

import json
import logging
import optparse
import os
import sys
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

default_timeout_in_seconds = 60 * 60
seconds_to_wait = 3

def get_parser():
    parser = optparse.OptionParser(
        description=__doc__,
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

    parser.add_option('-H', '--debug-http', dest='debug_http', default=False,
        action='store_true', help=textwrap.dedent('''\
        Output the HTTP request/response headers on stderr'''))

    return parser

def add_globalopts(parser):
    '''
    Misc global options
    '''
    optgroup = optparse.OptionGroup(parser, "Pepper ``salt`` Options",
            "Mimic the ``salt`` CLI")

    optgroup.add_option('-t', '--timeout', dest='timeout', type ='int',
        help="Specify wait time (in seconds) before returning control to the shell")

    #optgroup.add_option('--out', '--output', dest='output',
    #        help="Specify the output format for the command output")

    #optgroup.add_option('--return', default='', metavar='RETURNER',
    #    help="Redirect the output from a command to a persistent data store")

    optgroup.add_option('--fail-if-incomplete', action='store_true',
        dest='fail_if_minions_dont_respond',
        help="Optional, return a failure exit code if not all minions respond")

    parser.set_defaults(timeout=default_timeout_in_seconds)
    parser.set_defaults(fail_if_minions_dont_respond=False)
    parser.add_option_group(optgroup)

def add_tgtopts(parser):
    '''
    Targeting
    '''
    optgroup = optparse.OptionGroup(parser, "Targeting Options",
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

    parser.set_defaults(expr_form='glob')
    parser.add_option_group(optgroup)

def add_authopts(parser):
    '''
    Authentication options
    '''
    optgroup = optparse.OptionGroup(parser, "Authentication Options",
            textwrap.dedent("""\
            Authentication credentials can optionally be supplied via the
            environment variables:
            SALTAPI_URL, SALTAPI_USER, SALTAPI_PASS, SALTAPI_EAUTH.
            """))

    optgroup.add_option('--saltapi-url', dest='saltapiurl', default='https://localhost:8000/',
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
                Optional, fail rather than waiting for input"""),default=interactive_check)

    # optgroup.add_option('-T', '--make-token', default=False,
    #     dest='mktoken', action='store_true',
    #     help=textwrap.dedent("""\
    #         Generate and save an authentication token for re-use. The token is
    #         generated and made available for the period defined in the Salt
    #         Master."""))

    parser.add_option_group(optgroup)

def get_login_details(opts):
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

    profile = 'main'

    config = ConfigParser.RawConfigParser()
    config.read(opts.config)

    # read file
    if config.has_section(profile):
        for key, value in config.items(profile):
            key = key.upper()
            results[key] = config.get(profile, key)

    # get environment values
    for key, value in results.items():
        results[key] = os.environ.get(key, results[key])

    # get eauth prompt options
    if opts.saltapiurl:
        results['SALTAPI_URL'] = opts.saltapiurl

    if opts.eauth:
        results['SALTAPI_EAUTH'] = opts.eauth
        if opts.username == None:
          if opts.interactive:
            results['SALTAPI_USER'] = raw_input('Username: ')
          else:
            logger.error("SALTAPI_USER required")
            raise SystemExit(1)
        else:
          results['SALTAPI_USER'] = opts.username
        if opts.password == None:
          if opts.interactive:
            results['SALTAPI_PASS'] = getpass.getpass(prompt='Password: ')
          else:
            logger.error("SALTAPI_PASS required")
            raise SystemExit(1)
        else:
          results['SALTAPI_PASS'] = opts.password

    return results

def pepper_main():
    '''
    '''
    global interactive_check
    if hasattr(pepper_main, '__file__'):
      interactive_check = False
    else:
      interactive_check = True

    parser = get_parser()

    add_globalopts(parser)
    add_tgtopts(parser)
    add_authopts(parser)

    opts, args = parser.parse_args()

    logger.addHandler(logging.StreamHandler())
    logger.setLevel(max(logging.ERROR - (opts.verbose * 10), 1))

    if len(args) < 2:
        parser.error("Command not recognized.")

    tgt, fun = args.pop(0), args.pop(0)

    login_details = get_login_details(opts)

    # Auth values placeholder; grab interactively at CLI or from config file
    salturl = login_details['SALTAPI_URL']
    saltuser = login_details['SALTAPI_USER']
    saltpass = login_details['SALTAPI_PASS']
    salteauth = login_details['SALTAPI_EAUTH']

    api = pepper.Pepper(salturl, debug_http=opts.debug_http)
    auth = api.login(saltuser, saltpass, salteauth)
    nodesJidRet = api.local_async(tgt=tgt, fun='test.ping', expr_form=opts.expr_form)
    nodesJid = nodesJidRet['return'][0]['jid']
    time.sleep(seconds_to_wait)
    nodesRet = api.lookup_jid(nodesJid)
    if fun == 'test.ping':
        return (0,json.dumps(nodesRet['return'][0], sort_keys=True, indent=4))
    nodes = nodesRet['return'][0].keys()
    if nodes == []:
        return (0,json.dumps({}))
    commandJidRet = api.local_async(tgt=nodes, fun=fun, arg=args, expr_form='list')
    commandJid = commandJidRet['return'][0]['jid']
    # keep trying until all expected nodes return
    commandRet = api.lookup_jid(commandJid)
    returnedNodes = commandRet['return'][0].keys()
    total_time = seconds_to_wait
    while set(returnedNodes) != set(nodes):
      if total_time > opts.timeout :
         break
      time.sleep(seconds_to_wait)
      commandRet = api.lookup_jid(commandJid)
      returnedNodes = commandRet['return'][0].keys()

    if set(returnedNodes) != set(nodes) and opts.fail_if_minions_dont_respond is True:
         exit_code = 1
    else:
         exit_code = 0

    return (exit_code,json.dumps(commandRet['return'][0], sort_keys=True, indent=4))
