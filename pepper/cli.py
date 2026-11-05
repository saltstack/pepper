"""
A CLI interface to a remote salt-api instance

"""

import getpass
import json
import logging
import optparse  # pylint: disable=deprecated-module
import os
import sys
import tempfile
import textwrap
import time
from configparser import ConfigParser
from json import JSONDecodeError

import pepper
from pepper.exceptions import (
    PepperArgumentsException,
    PepperAuthException,
    PepperException,
)

logger = logging.getLogger(__name__)

LOG_FORMAT = "%(levelname)s %(asctime)s %(module)s: %(message)s"


class _StderrHandler(logging.StreamHandler):
    """
    A handler that writes to whatever sys.stderr is when a record is logged
    """

    def __init__(self):
        super().__init__(sys.stderr)

    @property
    def stream(self):
        return sys.stderr

    @stream.setter
    def stream(self, value):
        pass


class PepperCli:
    def __init__(self, seconds_to_wait=3):
        self.seconds_to_wait = seconds_to_wait
        self._cached_auth = False
        self._cache_key = None
        self.parser = self.get_parser()
        self.parser.option_groups.extend(
            [
                self.add_globalopts(),
                self.add_tgtopts(),
                self.add_authopts(),
                self.add_retcodeopts(),
            ]
        )
        self.parse()

    def get_parser(self):
        # Name the program pepper, not __main__.py, under python -m pepper
        return optparse.OptionParser(
            prog="pepper",
            description=__doc__,
            usage="%prog [opts]",
            version=pepper.__version__,
        )

    def parse(self):
        """
        Parse all args
        """
        self.parser.add_option(
            "-c",
            dest="config",
            default=os.environ.get(
                "PEPPERRC", os.path.join(os.path.expanduser("~"), ".pepperrc")
            ),
            help=textwrap.dedent(
                """
                Configuration file location. Default is a file path in the
                "PEPPERRC" environment variable or ~/.pepperrc.
            """
            ),
        )

        self.parser.add_option(
            "-p",
            dest="profile",
            default=os.environ.get("PEPPERPROFILE", "main"),
            help=textwrap.dedent(
                """
                Profile in config file to use. Default is "PEPPERPROFILE" environment
                variable or 'main'
            """
            ),
        )

        self.parser.add_option(
            "-m",
            dest="master",
            default=os.environ.get(
                "MASTER_CONFIG",
                os.path.join(os.path.expanduser("~"), ".config", "pepper", "master"),
            ),
            help=textwrap.dedent(
                """
                Master Configuration file location for configuring outputters.
                default: ~/.config/pepper/master
            """
            ),
        )

        self.parser.add_option(
            "-o",
            "--out",
            dest="output",
            default=None,
            help=textwrap.dedent(
                """
                Salt outputter to use for printing out returns.
            """
            ),
        )

        self.parser.add_option(
            "--output-file",
            dest="output_file",
            default=None,
            help=textwrap.dedent(
                """
                File to put command output in
            """
            ),
        )

        self.parser.add_option(
            "-v",
            dest="verbose",
            default=0,
            action="count",
            help=textwrap.dedent(
                """
                Increment output verbosity; may be specified multiple times
            """
            ),
        )

        self.parser.add_option(
            "-H",
            "--debug-http",
            dest="debug_http",
            default=False,
            action="store_true",
            help=textwrap.dedent(
                """
                Output the HTTP request/response headers on stderr
            """
            ),
        )

        self.parser.add_option(
            "--ignore-ssl-errors",
            action="store_true",
            dest="ignore_ssl_certificate_errors",
            default=False,
            help=textwrap.dedent(
                """
                Do not verify the salt-api TLS certificate. Certificates are
                verified by default.
            """
            ),
        )

        self.parser.add_option(
            "--ca-bundle",
            dest="ca_bundle",
            default=None,
            help=textwrap.dedent(
                """
                A file of PEM CA certificates, or a directory of them prepared
                with c_rehash, to verify the salt-api certificate with instead of
                the system's trusted CA certificates. Can also be set with
                SALTAPI_CA_BUNDLE.
            """
            ),
        )

        self.parser.add_option(
            "--client-cert",
            dest="client_cert",
            default=None,
            help=textwrap.dedent(
                """
                A PEM file with a client certificate to present to salt-api. It
                must also contain the private key unless --client-cert-key is
                given. Can also be set with SALTAPI_CLIENT_CERT.
            """
            ),
        )

        self.parser.add_option(
            "--client-cert-key",
            dest="client_cert_key",
            default=None,
            help=textwrap.dedent(
                """
                A PEM file with the private key for --client-cert. Can also be
                set with SALTAPI_CLIENT_CERT_KEY.
            """
            ),
        )

        self.options, self.args = self.parser.parse_args()

        option_names = ["fail_any", "fail_any_none", "fail_all", "fail_all_none"]
        toggled_options = [name for name in option_names if getattr(self.options, name)]
        if len(toggled_options) > 1:
            s = repr(toggled_options).strip("[]")
            self.parser.error("Options %s are mutually exclusive" % s)

    def add_globalopts(self):
        """
        Misc global options
        """
        optgroup = optparse.OptionGroup(
            self.parser, "Pepper ``salt`` Options", "Mimic the ``salt`` CLI"
        )

        optgroup.add_option(
            "-t",
            "--timeout",
            dest="timeout",
            type="int",
            default=60,
            help=textwrap.dedent(
                """
                How long to wait for minions to return, in seconds. As with
                salt -t, minions that are still running the job are waited for
                beyond this. Add --fail-if-incomplete to stop waiting after this
                long and report the minions that did not return.
            """
            ),
        )

        optgroup.add_option(
            "--client",
            dest="client",
            default="local",
            help=textwrap.dedent(
                """
                specify the salt-api client to use (local, local_async,
                runner, etc)
            """
            ),
        )

        optgroup.add_option(
            "--json",
            dest="json_input",
            help=textwrap.dedent(
                """
                Enter JSON at the CLI instead of positional (text) arguments. This
                is useful for arguments that need complex data structures.
                Specifying this argument will cause positional arguments to be
                ignored.
            """
            ),
        )

        optgroup.add_option(
            "--json-file",
            dest="json_file",
            help=textwrap.dedent(
                """
                Specify file containing the JSON to be used by pepper
            """
            ),
        )

        optgroup.add_option(
            "--fail-if-incomplete",
            action="store_true",
            dest="fail_if_minions_dont_respond",
            default=False,
            help=textwrap.dedent(
                """
                Send the command with the local_async client, poll for returns
                with the jobs.lookup_jid runner until all targeted minions
                respond or --timeout passes, and exit with a failure code if
                any did not respond. Only works with a single command for the
                local client, and requires permission to run the
                jobs.lookup_jid runner function. jobs.lookup_jid returns no
                retcodes, so this cannot be combined with the --fail-* options.
            """
            ),
        )

        return optgroup

    def add_tgtopts(self):
        """
        Targeting
        """
        optgroup = optparse.OptionGroup(
            self.parser, "Targeting Options", "Target which minions to run commands on"
        )

        optgroup.defaults.update({"tgt_type": "glob"})

        optgroup.add_option(
            "-E",
            "--pcre",
            dest="tgt_type",
            action="store_const",
            const="pcre",
            help="Target hostnames using PCRE regular expressions",
        )

        optgroup.add_option(
            "-L",
            "--list",
            dest="tgt_type",
            action="store_const",
            const="list",
            help="Specify a comma delimited list of hostnames",
        )

        optgroup.add_option(
            "-G",
            "--grain",
            dest="tgt_type",
            action="store_const",
            const="grain",
            help="Target based on system properties",
        )

        optgroup.add_option(
            "--grain-pcre",
            dest="tgt_type",
            action="store_const",
            const="grain_pcre",
            help="Target based on PCRE matches on system properties",
        )

        optgroup.add_option(
            "-I",
            "--pillar",
            dest="tgt_type",
            action="store_const",
            const="pillar",
            help="Target based on pillar values",
        )

        optgroup.add_option(
            "--pillar-pcre",
            dest="tgt_type",
            action="store_const",
            const="pillar_pcre",
            help="Target based on PCRE matches on pillar values",
        )

        optgroup.add_option(
            "-R",
            "--range",
            dest="tgt_type",
            action="store_const",
            const="range",
            help="Target based on range expression",
        )

        optgroup.add_option(
            "-C",
            "--compound",
            dest="tgt_type",
            action="store_const",
            const="compound",
            help="Target based on compound expression",
        )

        optgroup.add_option(
            "-N",
            "--nodegroup",
            dest="tgt_type",
            action="store_const",
            const="nodegroup",
            help="Target based on a named nodegroup",
        )

        optgroup.add_option("--batch", dest="batch", default=None)

        return optgroup

    def add_authopts(self):
        """
        Authentication options
        """
        optgroup = optparse.OptionGroup(
            self.parser,
            "Authentication Options",
            textwrap.dedent(
                """
                Authentication credentials can optionally be supplied via the
                environment variables:
                SALTAPI_URL, SALTAPI_USER, SALTAPI_PASS, SALTAPI_EAUTH.
            """
            ),
        )

        optgroup.add_option(
            "-u",
            "--saltapi-url",
            dest="saltapiurl",
            help="Specify the host url.  Defaults to https://localhost:8080",
        )

        optgroup.add_option(
            "-a",
            "--auth",
            "--eauth",
            "--extended-auth",
            dest="eauth",
            help=textwrap.dedent(
                """
                Specify the external_auth backend to authenticate against and
                interactively prompt for credentials
            """
            ),
        )

        optgroup.add_option(
            "--username",
            dest="username",
            help=textwrap.dedent(
                """
                Optional, defaults to user name. will be prompt if empty unless --non-interactive
            """
            ),
        )

        optgroup.add_option(
            "--password",
            dest="password",
            help=textwrap.dedent(
                """
                Optional, but will be prompted unless --non-interactive
            """
            ),
        )

        optgroup.add_option(
            "--token-expire",
            dest="token_expire",
            help=textwrap.dedent(
                """
                Set eauth token expiry in seconds. Must be allowed per
                user. See the `token_expire_user_override` Master setting
                for more info.
            """
            ),
        )

        optgroup.add_option(
            "--non-interactive",
            action="store_false",
            dest="interactive",
            default=True,
            help=textwrap.dedent(
                """
                Optional, fail rather than waiting for input
            """
            ),
        )

        optgroup.add_option(
            "-T",
            "--make-token",
            default=False,
            dest="mktoken",
            action="store_true",
            help=textwrap.dedent(
                """
                Generate and save an authentication token for re-use. The token is
                generated and made available for the period defined in the Salt
                Master.
            """
            ),
        )

        optgroup.add_option(
            "-r",
            "--run-uri",
            default=False,
            dest="userun",
            action="store_true",
            help=textwrap.dedent(
                """
                Use an eauth token from /token and send commands through the
                /run URL instead of the traditional session token
                approach.
            """
            ),
        )

        optgroup.add_option(
            "-x",
            dest="cache",
            default=os.environ.get(
                "PEPPERCACHE", os.path.join(os.path.expanduser("~"), ".peppercache")
            ),
            help=textwrap.dedent(
                """
                Token cache file for --make-token. It holds one token for each
                salt-api URL, user and eauth. Default is a file path in the
                "PEPPERCACHE" environment variable or ~/.peppercache.
            """
            ),
        )

        return optgroup

    def add_retcodeopts(self):
        """
        ret code validation options
        """
        optgroup = optparse.OptionGroup(
            self.parser,
            "retcode Field Validation Options",
            "Validate return.HOST.retcode fields",
        )

        optgroup.add_option(
            "--fail-any",
            dest="fail_any",
            action="store_true",
            help="Fail if any of retcode field is non zero.",
        )

        optgroup.add_option(
            "--fail-any-none",
            dest="fail_any_none",
            action="store_true",
            help="Fail if any of retcode field is non zero or there is no retcode at all.",
        )

        optgroup.add_option(
            "--fail-all",
            dest="fail_all",
            action="store_true",
            help="Fail if all retcode fields are non zero.",
        )

        optgroup.add_option(
            "--fail-all-none",
            dest="fail_all_none",
            action="store_true",
            help="Fail if all retcode fields are non zero or there is no retcode at all.",
        )

        return optgroup

    def get_config(self, defaults):
        """
        Read settings from the selected profile of the config file, then from
        the environment, which takes precedence

        :param defaults: a dict of setting names and their default values
        """
        config = ConfigParser(interpolation=None)
        config.read(self.options.config)
        profile = self.options.profile

        results = dict(defaults)
        for key in results:
            if config.has_section(profile) and config.has_option(profile, key):
                results[key] = config.get(profile, key)
            results[key] = os.environ.get(key, results[key])
        return results

    def get_login_details(self):
        """
        This parses the config file, environment variables and command line options
        and returns the config values
        Order of parsing:
            command line options, ~/.pepperrc, environment, defaults
        """

        results = self.get_config(
            {
                "SALTAPI_USER": None,
                "SALTAPI_PASS": None,
                "SALTAPI_EAUTH": "auto",
            }
        )

        if results["SALTAPI_EAUTH"] == "kerberos":
            results["SALTAPI_PASS"] = None

        if self.options.eauth:
            results["SALTAPI_EAUTH"] = self.options.eauth
        if self.options.token_expire:
            results["SALTAPI_TOKEN_EXPIRE"] = self.options.token_expire
        if self.options.username is None and results["SALTAPI_USER"] is None:
            if self.options.interactive:
                results["SALTAPI_USER"] = input("Username: ")
            else:
                raise PepperAuthException("SALTAPI_USER required")
        else:
            if self.options.username is not None:
                results["SALTAPI_USER"] = self.options.username
        if (
            self.options.password is None
            and results["SALTAPI_PASS"] is None
            and results["SALTAPI_EAUTH"] != "kerberos"
        ):
            if self.options.interactive:
                results["SALTAPI_PASS"] = getpass.getpass(prompt="Password: ")
            else:
                raise PepperAuthException("SALTAPI_PASS required")
        else:
            if self.options.password is not None:
                results["SALTAPI_PASS"] = self.options.password

        return results

    def parse_url(self):
        """
        Determine api url
        """
        url = self.get_config({"SALTAPI_URL": "https://localhost:8000/"})["SALTAPI_URL"]

        # get eauth prompt options
        if self.options.saltapiurl:
            url = self.options.saltapiurl

        return url

    def parse_tls(self):
        """
        Determine the CA bundle and client certificate for salt-api
        """
        results = self.get_config(
            {
                "SALTAPI_CA_BUNDLE": None,
                "SALTAPI_CLIENT_CERT": None,
                "SALTAPI_CLIENT_CERT_KEY": None,
            }
        )
        tls = {
            "ca_bundle": self.options.ca_bundle or results["SALTAPI_CA_BUNDLE"],
            "client_cert": self.options.client_cert or results["SALTAPI_CLIENT_CERT"],
            "client_cert_key": self.options.client_cert_key
            or results["SALTAPI_CLIENT_CERT_KEY"],
        }
        if tls["client_cert_key"] and not tls["client_cert"]:
            raise PepperArgumentsException(
                "A client certificate key was given without a client certificate"
            )
        return tls

    def parse_login(self):
        """
        Extract the authentication credentials
        """
        login_details = self.get_login_details()

        # Auth values placeholder; grab interactively at CLI or from config
        username = login_details["SALTAPI_USER"]
        password = login_details["SALTAPI_PASS"]
        eauth = login_details["SALTAPI_EAUTH"]

        ret = dict(username=username, password=password, eauth=eauth)

        token_expire = login_details.get("SALTAPI_TOKEN_EXPIRE", None)
        if token_expire:
            ret["token_expire"] = int(token_expire)

        return ret

    def parse_cmd(self, api):
        """
        Extract the low data for a command from the passed CLI params
        """
        # Short-circuit if JSON was given.
        if self.options.json_input:
            try:
                return json.loads(self.options.json_input)
            except JSONDecodeError:
                raise PepperArgumentsException("Invalid JSON given.")

        if self.options.json_file:
            try:
                with open(self.options.json_file, encoding="utf-8") as json_content:
                    try:
                        return json.load(json_content)
                    except (JSONDecodeError, UnicodeDecodeError):
                        raise PepperArgumentsException("Invalid JSON given.")
            except FileNotFoundError:
                raise PepperArgumentsException(
                    f"Cannot open file: {self.options.json_file}"
                )

        args = list(self.args)

        client = self.options.client if not self.options.batch else "local_batch"
        low = {"client": client}

        if client.startswith("local"):
            if len(args) < 2:
                self.parser.error("Command or target not specified")

            low["tgt_type"] = self.options.tgt_type
            low["tgt"] = args.pop(0)
            low["fun"] = args.pop(0)
            low["batch"] = self.options.batch
            low["arg"] = args
        elif client.startswith("runner"):
            low["fun"] = args.pop(0)
            # post https://github.com/saltstack/salt/pull/50124, kwargs can be
            # passed as is in foo=bar form, splitting and deserializing will
            # happen in salt-api. additionally, the presence of salt-version header
            # means we are neon or newer, so don't need a finer grained check
            if api.salt_version:
                low["arg"] = args
            else:
                for arg in args:
                    if "=" in arg:
                        key, value = arg.split("=", 1)
                        try:
                            low[key] = json.loads(value)
                        except JSONDecodeError:
                            low[key] = value
                    else:
                        low.setdefault("arg", []).append(arg)
        elif client.startswith("wheel"):
            low["fun"] = args.pop(0)
            # see above comment in runner arg handling
            if api.salt_version:
                low["arg"] = args
            else:
                for arg in args:
                    if "=" in arg:
                        key, value = arg.split("=", 1)
                        try:
                            low[key] = json.loads(value)
                        except JSONDecodeError:
                            low[key] = value
                    else:
                        low.setdefault("arg", []).append(arg)
        elif client.startswith("ssh"):
            if len(args) < 2:
                self.parser.error("Command or target not specified")

            low["tgt_type"] = self.options.tgt_type
            low["tgt"] = args.pop(0)
            low["fun"] = args.pop(0)
            low["batch"] = self.options.batch
            low["arg"] = args
        else:
            raise PepperException(f"Client not implemented: {client}")

        return [low]

    def poll_for_returns(self, api, load):
        """
        Run a command with the local_async client and periodically poll the job
        cache for returns for the job.
        """
        if len(load) != 1 or load[0].get("client") not in ("local", "local_async"):
            raise PepperArgumentsException(
                "--fail-if-incomplete only works with a single command for the "
                "local client"
            )
        if any(
            (
                self.options.fail_any,
                self.options.fail_any_none,
                self.options.fail_all,
                self.options.fail_all_none,
            )
        ):
            raise PepperArgumentsException(
                "--fail-if-incomplete cannot be used with the --fail-* retcode "
                "options, because jobs.lookup_jid returns no retcodes"
            )
        load[0]["client"] = "local_async"
        async_ret = self._call(api, self.low, api, load)
        job = async_ret["return"][0]
        if not isinstance(job, dict) or "jid" not in job:
            # No minions matched; the empty return says so, as for the local
            # client, and exits with 2
            yield 2, [job]
            return
        jid = job["jid"]
        nodes = job["minions"]
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

            jid_ret = self.low(
                api,
                [
                    {
                        "client": "runner",
                        "fun": "jobs.lookup_jid",
                        "kwarg": {
                            "jid": jid,
                        },
                    }
                ],
            )

            inner_ret = jid_ret["return"][0]
            # sometimes ret is nested in data
            if "data" in inner_ret:
                inner_ret = inner_ret["data"]

            responded = set(inner_ret.keys()) ^ set(ret_nodes)

            for node in responded:
                yield None, [{node: inner_ret[node]}]
            ret_nodes = list(inner_ret.keys())

            if set(ret_nodes) == set(nodes):
                exit_code = 0
                break
            else:
                time.sleep(self.seconds_to_wait)

        exit_code = exit_code if self.options.fail_if_minions_dont_respond else 0
        failed = sorted(set(ret_nodes) ^ set(nodes))
        yield exit_code, [{"Failed": failed}] if failed else []

    def _login_user(self):
        """
        The username to log in as, prompting for it if it is not configured

        A prompted name is kept in the options, so get_login_details() does not
        ask again.
        """
        user = self.options.username
        if user is None:
            user = self.get_config({"SALTAPI_USER": None})["SALTAPI_USER"]
        if user is None and self.options.interactive:
            user = self.options.username = input("Username: ")
        return user

    def _token_cache_key(self, api, user):
        """
        Identify the cached token for the salt-api URL, user and eauth in use,
        and whether it is a /login session token or a /token eauth token for
        --run-uri
        """
        eauth = (
            self.options.eauth
            or self.get_config({"SALTAPI_EAUTH": "auto"})["SALTAPI_EAUTH"]
        )
        kind = "run" if self.options.userun else "login"
        return json.dumps([api.api_url, user, eauth, kind])

    @staticmethod
    def _token_expire(entry):
        """
        The expiry time of a cached token, 0 if it is missing or not a number
        """
        try:
            return float(entry["auth"].get("expire", 0))
        except (TypeError, ValueError):
            return 0

    def _read_token_cache(self):
        """
        Return the cached tokens, as a dict of cache keys to entries with the
        login response in "auth" and the salt-api version in "salt_version"
        """
        try:
            with open(self.options.cache, encoding="utf-8") as cache_file:
                cache = json.load(cache_file)
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as exc:
            logger.error(
                "Unable to load login tokens from %s: %s", self.options.cache, exc
            )
            return {}
        if not isinstance(cache, dict):
            return {}
        # Earlier versions stored a single login response without the salt-api
        # it belongs to, which is skipped here
        return {
            key: entry
            for key, entry in cache.items()
            if isinstance(entry, dict) and isinstance(entry.get("auth"), dict)
        }

    def _write_token_cache(self, cache):
        """
        Replace the token cache file, dropping expired tokens

        The file is written to a temporary file in the same directory, which
        mkstemp creates readable by the owner only, and then renamed over the
        cache file so readers never see a partial file.
        """
        now = time.time()
        cache = {
            key: entry
            for key, entry in cache.items()
            if self._token_expire(entry) > now
        }
        directory = os.path.dirname(os.path.abspath(self.options.cache))
        try:
            fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".peppercache-")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as cache_file:
                    json.dump(cache, cache_file)
                os.replace(tmp_path, self.options.cache)
            except BaseException:
                os.unlink(tmp_path)
                raise
        except OSError as exc:
            logger.error(
                "Unable to save login token to %s: %s", self.options.cache, exc
            )

    def login(self, api, use_cache=True):
        login = api.token if self.options.userun else api.login
        self._cached_auth = False
        self._cache_key = None

        user = self._login_user() if self.options.mktoken else None
        if user is None:
            # No token cache, or no user to key it by, in which case
            # get_login_details() reports the missing user
            auth = login(**self.parse_login())
        else:
            key = self._token_cache_key(api, user)
            cache = self._read_token_cache()
            entry = cache.get(key) if use_cache else None
            if entry and self._token_expire(entry) > time.time() + 30:
                auth = entry["auth"]
                # The salt-api version normally comes with the login response.
                # parse_cmd() and low() need it to pass arguments and the
                # timeout the way current salt-api expects.
                if entry.get("salt_version") and not api.salt_version:
                    api.salt_version = tuple(entry["salt_version"])
                self._cached_auth = True
                self._cache_key = key
            else:
                auth = login(**self.parse_login())
                if auth.get("token"):
                    cache[key] = {"auth": auth, "salt_version": api.salt_version}
                    self._write_token_cache(cache)

        api.auth = auth
        self.auth = auth
        return auth

    def _call(self, api, func, *args):
        """
        Call func, logging in again once if salt-api rejects a cached token

        salt-api forgets tokens when it restarts or its token store is
        cleared, so a token that has not expired can still be refused. It
        also answers 401 when the user may not run the command, so the cached
        token is only replaced by a successful login, and the original error
        is raised when there are no credentials to log in with.
        """
        try:
            return func(*args)
        except PepperAuthException as exc:
            if not self._cached_auth:
                raise
            logger.warning("salt-api rejected the cached token, logging in again")
            key = self._cache_key
            try:
                self.login(api, use_cache=False)
            except PepperAuthException:
                # Do not offer the rejected token again on the next run
                cache = self._read_token_cache()
                if cache.pop(key, None) is not None:
                    self._write_token_cache(cache)
                raise exc
            return func(*args)

    def low(self, api, load):
        path = "/run" if self.options.userun else "/"

        if self.options.userun:
            for i in load:
                i["token"] = self.auth["token"]

        # having a defined salt_version means changes from https://github.com/saltstack/salt/pull/51979
        # are available if backend is tornado, so safe to supply timeout
        if self.options.timeout and api.salt_version:
            for i in load:
                if not i.get("client", "").startswith("wheel"):
                    i["timeout"] = self.options.timeout

        return api.low(load, path=path)

    def run(self):
        """
        Parse all arguments and call salt-api
        """
        # Log pepper's messages through one handler on the pepper logger, set
        # up once since run() can be called more than once in a process. They
        # do not propagate to the root logger, where importing salt installs a
        # handler of its own that would print them a second time.
        pepper_logger = logging.getLogger("pepper")
        if not any(isinstance(h, _StderrHandler) for h in pepper_logger.handlers):
            handler = _StderrHandler()
            handler.setFormatter(logging.Formatter(LOG_FORMAT))
            pepper_logger.addHandler(handler)
        pepper_logger.propagate = False
        pepper_logger.setLevel(max(logging.ERROR - (self.options.verbose * 10), 1))

        api = pepper.Pepper(
            self.parse_url(),
            debug_http=self.options.debug_http,
            ignore_ssl_errors=self.options.ignore_ssl_certificate_errors,
            **self.parse_tls(),
        )

        self.login(api)

        load = self.parse_cmd(api)

        for entry in load:
            if not entry.get("client", "").startswith("wheel"):
                entry["full_return"] = True

        if self.options.fail_if_minions_dont_respond:
            for exit_code, ret in self.poll_for_returns(api, load):  # pragma: no cover
                yield exit_code, json.dumps(ret, sort_keys=True, indent=4)
        else:
            ret = self._call(api, self.low, api, load)
            exit_code = 0
            yield exit_code, json.dumps(ret, sort_keys=True, indent=4)
