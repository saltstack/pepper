"""
A Python library for working with Salt's REST API

(Specifically the rest_cherrypy netapi module.)

"""

import html
import http.client
import json
import logging
import os
import re
import ssl
import sys
import urllib.parse as urlparse
import warnings
from urllib.error import HTTPError, URLError
from urllib.request import (
    HTTPHandler,
    HTTPRedirectHandler,
    HTTPSHandler,
    Request,
    build_opener,
)

from pepper import config
from pepper.exceptions import PepperAuthException, PepperException

logger = logging.getLogger(__name__)

#: Headers that carry credentials, which are not sent on to another host
AUTH_HEADERS = ("x-auth-token", "authorization")

_REDACT_HEADERS = re.compile(
    r"(?im)^((?:x-auth-token|authorization|cookie|set-cookie)[ \t]*:[ \t]*)[^\r\n]*"
)
_REDACT_JSON = re.compile(r'("(?:password|token)"\s*:\s*)"(?:[^"\\]|\\.)*"')


def redact(text):
    """
    Replace passwords, tokens and session cookies in HTTP headers and JSON
    bodies with [redacted]

    :param text: a str, or bytes, which are decoded as latin-1
    """
    if isinstance(text, bytes):
        text = text.decode("latin-1")
    text = _REDACT_HEADERS.sub(r"\1[redacted]", text)
    return _REDACT_JSON.sub(r'\1"[redacted]"', text)


class _DebugResponse(http.client.HTTPResponse):
    """
    A response that prints its status and headers with debug_http, with
    session cookies redacted, to stderr
    """

    def begin(self):
        level, self.debuglevel = self.debuglevel, 0
        try:
            super().begin()
        finally:
            self.debuglevel = level
        if level > 0:
            print("reply:", self.status, self.reason, file=sys.stderr)
            for name, value in self.headers.items():
                print("header:", redact(f"{name}: {value}"), file=sys.stderr)


class _DebugConnectionMixin:
    """
    Print what is sent with debug_http, with the password and token redacted,
    to stderr instead of http.client's own output to stdout
    """

    response_class = _DebugResponse

    def send(self, data):
        if self.debuglevel <= 0:
            return super().send(data)
        print("send:", repr(redact(data)), file=sys.stderr)
        level, self.debuglevel = self.debuglevel, 0
        try:
            return super().send(data)
        finally:
            self.debuglevel = level


class _HTTPConnection(_DebugConnectionMixin, http.client.HTTPConnection):
    pass


class _HTTPSConnection(_DebugConnectionMixin, http.client.HTTPSConnection):
    pass


class _HTTPHandler(HTTPHandler):
    def http_open(self, req):
        return self.do_open(_HTTPConnection, req)


class _LazyHTTPSHandler(HTTPSHandler):
    """
    An HTTPS handler that only builds its SSL context when it opens an HTTPS
    connection, so a plain HTTP salt-api URL never loads the TLS files and a
    redirect from HTTP to HTTPS still uses the TLS options
    """

    def __init__(self, get_context, debuglevel=0):
        super().__init__(debuglevel=debuglevel)
        self._get_context = get_context

    def https_open(self, req):
        return self.do_open(_HTTPSConnection, req, context=self._get_context())


def _origin(url):
    """
    The scheme, host and port of a URL, with the default port filled in
    """
    split = urlparse.urlsplit(url)
    scheme = split.scheme.lower()
    port = split.port or {"http": 80, "https": 443}.get(scheme)
    return scheme, (split.hostname or "").lower(), port


class _RedirectHandler(HTTPRedirectHandler):
    """
    Follow redirects like urllib, but refuse to go from HTTPS to HTTP and do
    not send credentials on to another host, the way requests handles the
    Authorization header
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old_scheme, old_host, old_port = _origin(req.full_url)
        new_scheme, new_host, new_port = _origin(urlparse.urljoin(req.full_url, newurl))
        if old_scheme == "https" and new_scheme != "https":
            raise PepperException(
                f"Refusing to follow a redirect from {req.full_url} to {newurl}, "
                "which is not HTTPS"
            )
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_req is None:
            return None
        # As requests does, an upgrade from http to https on the default
        # ports of the same host counts as the same host
        upgrade = (old_scheme, old_port, new_scheme, new_port) == (
            "http",
            80,
            "https",
            443,
        )
        if new_host != old_host or (new_port != old_port and not upgrade):
            for name in list(new_req.headers):
                if name.lower() in AUTH_HEADERS:
                    del new_req.headers[name]
        return new_req


def _parse_event_stream(lines):
    """
    Parse a server-sent event stream from salt-api into events

    salt-api sends each event as a ``tag:`` line and a ``data:`` line with the
    JSON event, followed by a blank line.
    """
    data = []
    for line in lines:
        if not line:
            if data:
                yield _event_json("\n".join(data))
            data = []
        elif line.startswith("data:"):
            data.append(line[5:].lstrip(" "))
    if data:
        yield _event_json("\n".join(data))


def _event_json(data):
    try:
        return json.loads(data)
    except ValueError:
        raise PepperException(f"Unable to parse event from salt-api: {data[:200]}")


def _error_detail(body):
    """
    Extract the error message from a salt-api error response body

    rest_cherrypy answers unexpected errors with JSON and other errors with
    CherryPy's HTML error page, which has the message in its first paragraph.
    rest_tornado uses Tornado's HTML error page.
    """
    if not body:
        return ""
    try:
        data = json.loads(body)
    except ValueError:
        match = re.search(r"<p>(.*?)</p>", body, re.S) or re.search(
            r"<body>(.*?)</body>", body, re.S
        )
        text = match.group(1) if match else body
        text = html.unescape(re.sub(r"<[^>]+>", " ", text))
        return " ".join(text.split())[:500]
    if isinstance(data, dict) and "return" in data:
        detail = data["return"]
        return detail if isinstance(detail, str) else json.dumps(detail)
    return ""


class Pepper:
    """
    A thin wrapper for making HTTP calls to the salt-api rest_cherrpy REST
    interface

    >>> api = Pepper('https://localhost:8000')
    >>> api.login('saltdev', 'saltdev', 'pam')
    {"return": [
            {
                "eauth": "pam",
                "expire": 1370434219.714091,
                "perms": [
                    "test.*"
                ],
                "start": 1370391019.71409,
                "token": "c02a6f4397b5496ba06b70ae5fd1f2ab75de9237",
                "user": "saltdev"
            }
        ]
    }
    >>> api.low([{'client': 'local', 'tgt': '*', 'fun': 'test.ping'}])
    {u'return': [{u'ms-0': True,
              u'ms-1': True,
              u'ms-2': True,
              u'ms-3': True,
              u'ms-4': True}]}

    """

    def __init__(
        self,
        api_url="https://localhost:8000",
        debug_http=False,
        ignore_ssl_errors=False,
        ca_bundle=None,
        client_cert=None,
        client_cert_key=None,
    ):
        """
        Initialize the class with the URL of the API

        :param api_url: Host or IP address of the salt-api URL;
            include the port number

        :param debug_http: Add a flag to urllib to output the HTTP exchange

        :param ignore_ssl_errors: Do not verify the salt-api TLS certificate

        :param ca_bundle: A file of PEM CA certificates, or a directory of them
            prepared with ``c_rehash``, to verify the salt-api certificate with
            instead of the system's trusted CA certificates

        :param client_cert: A PEM file with the client certificate to present
            to salt-api, and its private key unless ``client_cert_key`` is set

        :param client_cert_key: A PEM file with the private key for
            ``client_cert``

        :raises PepperException: if the api_url is misformed, or
            client_cert_key is given without client_cert

        """
        split = urlparse.urlsplit(api_url)
        if split.scheme not in ["http", "https"]:
            raise PepperException(f"salt-api URL missing HTTP(s) protocol: {api_url}")
        if client_cert_key and not client_cert:
            raise PepperException("client_cert_key needs client_cert")

        self.api_url = api_url
        self.debug_http = int(debug_http)
        self._ssl_verify = not ignore_ssl_errors
        self._ca_bundle = ca_bundle
        self._client_cert = client_cert
        self._client_cert_key = client_cert_key
        self._context = None
        self.auth = {}
        self.salt_version = None

    @classmethod
    def from_config(
        cls, profile=None, path=None, login=True, environment=None, **kwargs
    ):
        """
        Create a client from a .pepperrc profile and the SALTAPI_* environment
        variables, the same way the pepper command does, and log in

        As with the pepper command, SALTAPI_* environment variables override
        the default profile. A profile named by the profile argument or
        PEPPERPROFILE keeps its own settings, and environment variables only
        fill in the ones it does not set, so an exported SALTAPI_URL cannot
        send its credentials to another salt-api.

        >>> api = Pepper.from_config(profile="prod")
        >>> api.local("*", "test.ping")

        :param profile: the profile to use, PEPPERPROFILE or main by default
        :param path: the config file, PEPPERRC or ~/.pepperrc by default
        :param login: log in with the configured credentials
        :param environment: True to let SALTAPI_* environment variables
            override any profile, False to ignore them, None (the default) for
            the rule above
        :param kwargs: other arguments for :class:`Pepper`, which take
            precedence over the config file

        :raises PepperException: if the config file was named, by path or
            PEPPERRC, and cannot be read, or the profile was named, by profile
            or PEPPERPROFILE, and is not in the file
        :raises PepperAuthException: if login is set and the user or password
            is not configured
        """
        settings = config.read(
            path=path, profile=profile, environment=environment, strict=True
        )
        options = {
            "ca_bundle": settings["SALTAPI_CA_BUNDLE"],
            "client_cert": settings["SALTAPI_CLIENT_CERT"],
            "client_cert_key": settings["SALTAPI_CLIENT_CERT_KEY"],
        }
        options.update(kwargs)
        api = cls(settings["SALTAPI_URL"], **options)

        if login:
            eauth = settings["SALTAPI_EAUTH"]
            password = None if eauth == "kerberos" else settings["SALTAPI_PASS"]
            if settings["SALTAPI_USER"] is None:
                raise PepperAuthException("SALTAPI_USER required")
            if password is None and eauth != "kerberos":
                raise PepperAuthException("SALTAPI_PASS required")
            api.login(settings["SALTAPI_USER"], password, eauth)
        return api

    def req_stream(self, path):
        """
        A thin wrapper to get a response from saltstack api.
        The body of the response will not be downloaded immediately.
        Make sure to close the connection after use.
        api = Pepper('http://ipaddress/api/')
        print(api.login('salt','salt','pam'))
        response = api.req_stream('/events')

        :param path: The path to the salt api resource

        :return: :class:`Response <Response>` object

        :rtype: requests.Response

        :raises PepperException: if salt-api returns an error
        """
        return self._requests_get(path, stream=True)

    def events(self):
        """
        Yield events from salt-api's ``/events`` stream as they arrive

        Each event is a dict with the event ``tag`` and its ``data``. The
        stream stays open until the generator is closed or salt-api ends it,
        for example when the token expires. Needs requests.

        There is no timeout: on a quiet event bus the loop blocks until the
        next event, and salt-api sends nothing in between to keep the
        connection alive, so a dropped connection or a logged out token is
        only noticed when the next event is due. Leave the loop with
        ``break``, or call ``close()`` on the generator, to close the
        connection; from a terminal, Ctrl-C stops it.

        >>> for event in api.events():
        ...     if event["tag"].startswith("salt/job/"):
        ...         print(event["data"])

        :raises PepperException: if salt-api returns an error
        """
        resp = self.req_stream("/events")
        try:
            # Server-sent events are always UTF-8. Split the raw bytes, since
            # str.splitlines() also breaks lines at characters such as U+2028
            # that salt leaves unescaped in the JSON.
            yield from _parse_event_stream(
                line.decode("utf-8") for line in resp.iter_lines()
            )
        finally:
            resp.close()

    def req_get(self, path):
        """
        A thin wrapper from get http method of saltstack api
        api = Pepper('http://ipaddress/api/')
        print(api.login('salt','salt','pam'))
        print(api.req_get('/keys'))

        :raises PepperException: if salt-api returns an error
        """
        try:
            return self._requests_get(path).json()
        except ValueError:
            raise PepperException("Unable to parse the server response.")

    def _requests_get(self, path, stream=False):
        import requests

        if not (self.auth and self.auth.get("token")):
            raise PepperAuthException("Authentication required")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "X-Auth-Token": self.auth["token"],
        }
        url = self._construct_url(path)
        try:
            resp = requests.get(
                url=url,
                headers=headers,
                stream=stream,
                **self._requests_tls(),
            )
        except requests.exceptions.RequestException as exc:
            logger.debug("Error with request", exc_info=True)
            raise PepperException(f"Unable to connect to {url}: {exc}")
        if resp.status_code >= 400:
            raise self._http_error(resp.status_code, resp.reason, resp.text)
        return resp

    @staticmethod
    def _http_error(status, reason, body):
        """
        Return a PepperException describing an HTTP error from salt-api

        :param status: the HTTP status code
        :param reason: the HTTP reason phrase
        :param body: the response body text
        """
        exc_class = PepperException
        if status == 401:
            exc_class = PepperAuthException
            message = "Authentication denied"
        elif status == 500:
            message = "Server error"
        else:
            message = f"HTTP {status} {reason or ''}".strip()

        detail = _error_detail(body)
        if detail.lower() in ("", str(reason).lower(), f"{status}: {reason}".lower()):
            return exc_class(message)
        return exc_class(f"{message}: {detail}")

    def req(self, path, data=None):
        """
        A thin wrapper around urllib to send requests and return the response

        If the current instance contains an authentication token it will be
        attached to the request as a custom header.

        :rtype: dictionary

        """
        if (hasattr(data, "get") and data.get("eauth") == "kerberos") or self.auth.get(
            "eauth"
        ) == "kerberos":
            return self.req_requests(path, data)

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        }

        opener = build_opener(
            _HTTPHandler(debuglevel=self.debug_http),
            _LazyHTTPSHandler(self._ssl_context, debuglevel=self.debug_http),
            _RedirectHandler(),
        )

        # Build POST data
        if data is not None:
            postdata = json.dumps(data).encode()
            clen = len(postdata)
        else:
            postdata = None

        # Create request object
        url = self._construct_url(path)
        req = Request(url, postdata, headers)

        # Add POST data to request
        if data is not None:
            req.add_header("Content-Length", clen)

        # Add auth header to request
        if path != "/run" and self.auth and "token" in self.auth and self.auth["token"]:
            req.add_header("X-Auth-Token", self.auth["token"])

        # Send request
        try:
            f = opener.open(req)
            content = f.read().decode("utf-8")
            if self.debug_http:
                logger.debug("Response: %s", redact(content))
            ret = json.loads(content)

            if not self.salt_version and "x-salt-version" in f.headers:
                self._parse_salt_version(f.headers["x-salt-version"])

        except HTTPError as exc:
            logger.debug("Error with request", exc_info=True)
            body = exc.read().decode("utf-8", "replace")
            raise self._http_error(exc.code, exc.reason, body)
        except URLError as exc:
            logger.debug("Error with request", exc_info=True)
            if isinstance(exc.reason, ssl.SSLCertVerificationError):
                raise PepperException(
                    f"TLS certificate verification failed for {url}: "
                    f"{exc.reason.verify_message.rstrip('.')}. Use --ca-bundle "
                    "(ca_bundle) if it is signed by a private CA, or "
                    "--ignore-ssl-errors (ignore_ssl_errors=True) to skip "
                    "verification."
                )
            if isinstance(exc.reason, ssl.SSLError):
                raise PepperException(self._tls_error(url, exc.reason))
            raise PepperException(f"Unable to connect to {url}: {exc.reason}")
        except OSError as exc:
            # Errors after the request was sent, such as a TLS alert or a
            # dropped connection while reading the response. With TLS 1.3 the
            # server checks the client certificate after the handshake, so its
            # alert arrives here.
            logger.debug("Error with request", exc_info=True)
            if isinstance(exc, ssl.SSLError):
                raise PepperException(self._tls_error(url, exc))
            raise PepperException(f"Error talking to {url}: {exc}")
        except ValueError:
            logger.debug("Error converting response from JSON", exc_info=True)
            raise PepperException("Unable to parse the server response.")

        return ret

    @staticmethod
    def _tls_error(url, exc):
        """
        A message for a TLS error other than a failed certificate verification
        """
        reason = getattr(exc, "reason", None) or str(exc)
        message = f"TLS error from {url}: {reason}"
        if "CERTIFICATE_REQUIRED" in str(reason).upper():
            message += (
                ". The server requires a client certificate; use --client-cert "
                "(client_cert)."
            )
        return message

    def _ssl_context(self):
        """
        Return the SSL context for HTTPS requests

        It is built once per client, so an encrypted client key is only
        unlocked once.

        :raises PepperException: if the CA bundle or client certificate cannot
            be loaded
        """
        if self._context is not None:
            return self._context
        try:
            if self._ca_bundle and os.path.isdir(self._ca_bundle):
                context = ssl.create_default_context(capath=self._ca_bundle)
            else:
                context = ssl.create_default_context(cafile=self._ca_bundle)
        except (OSError, ssl.SSLError) as exc:
            raise PepperException(
                f"Unable to load the CA bundle {self._ca_bundle}: {exc}"
            )
        if not self._ssl_verify:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        if self._client_cert:
            try:
                context.load_cert_chain(self._client_cert, self._client_cert_key)
            except (OSError, ssl.SSLError) as exc:
                raise PepperException(
                    f"Unable to load the client certificate {self._client_cert}: {exc}"
                )
        self._context = context
        return context

    def _requests_tls(self):
        """
        Return the verify and cert arguments for requests
        """
        verify = self._ssl_verify and (self._ca_bundle or True)
        if self._client_cert and self._client_cert_key:
            cert = (self._client_cert, self._client_cert_key)
        else:
            cert = self._client_cert
        return {"verify": verify, "cert": cert}

    def req_requests(self, path, data=None):
        """
        A thin wrapper around request and request_kerberos to send
        requests and return the response

        If the current instance contains an authentication token it will be
        attached to the request as a custom header.

        :rtype: dictionary

        """
        import requests
        from requests_gssapi import OPTIONAL, HTTPSPNEGOAuth

        auth = HTTPSPNEGOAuth(mutual_authentication=OPTIONAL)
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        }
        if self.auth and "token" in self.auth and self.auth["token"]:
            headers.setdefault("X-Auth-Token", self.auth["token"])
        # Optionally toggle SSL verification
        params = {
            "url": self._construct_url(path),
            "headers": headers,
            **self._requests_tls(),
            "auth": auth,
            "data": json.dumps(data),
        }
        logger.debug("POST %s", params["url"])
        try:
            resp = requests.post(**params)
        except requests.exceptions.RequestException as exc:
            logger.debug("Error with request", exc_info=True)
            raise PepperException(f"Unable to connect to {params['url']}: {exc}")
        if resp.status_code >= 400:
            raise self._http_error(resp.status_code, resp.reason, resp.text)

        if not self.salt_version and "x-salt-version" in resp.headers:
            self._parse_salt_version(resp.headers["x-salt-version"])

        try:
            return resp.json()
        except ValueError:
            raise PepperException("Unable to parse the server response.")

    def low(self, lowstate, path="/"):
        """
        Execute a command through salt-api and return the response

        :param string path: URL path to be joined with the API hostname

        :param list lowstate: a list of lowstate dictionaries
        """
        return self.req(path, lowstate)

    def _local_low(
        self,
        client,
        tgt,
        fun,
        arg,
        kwarg,
        tgt_type,
        expr_form,
        full_return=False,
        **extra,
    ):
        """
        Build and send the low data for the local clients
        """
        if expr_form is not None:
            warnings.warn(
                "The expr_form argument is deprecated, use tgt_type instead. "
                "Salt 2019.2 and later ignore expr_form.",
                DeprecationWarning,
                stacklevel=3,
            )
            tgt_type = expr_form

        low = {
            "client": client,
            "tgt": tgt,
            "fun": fun,
        }

        if arg:
            low["arg"] = arg

        if kwarg:
            low["kwarg"] = kwarg

        if tgt_type:
            low["tgt_type"] = tgt_type

        if full_return:
            low["full_return"] = True

        low.update({key: value for key, value in extra.items() if value})

        return self.low([low])

    def local(
        self,
        tgt,
        fun,
        arg=None,
        kwarg=None,
        tgt_type="glob",
        timeout=None,
        ret=None,
        *,
        full_return=False,
        expr_form=None,
    ):
        """
        Run a single command using the ``local`` client

        Wraps :meth:`low`.

        :param full_return: Return the minion retcodes along with the results
        :param expr_form: Deprecated alias for ``tgt_type``
        """
        return self._local_low(
            "local",
            tgt,
            fun,
            arg,
            kwarg,
            tgt_type,
            expr_form,
            full_return,
            timeout=timeout,
            ret=ret,
        )

    def local_async(
        self,
        tgt,
        fun,
        arg=None,
        kwarg=None,
        tgt_type="glob",
        timeout=None,
        ret=None,
        *,
        expr_form=None,
    ):
        """
        Run a single command using the ``local_async`` client

        Wraps :meth:`low`.

        :param expr_form: Deprecated alias for ``tgt_type``
        """
        return self._local_low(
            "local_async",
            tgt,
            fun,
            arg,
            kwarg,
            tgt_type,
            expr_form,
            timeout=timeout,
            ret=ret,
        )

    def local_batch(
        self,
        tgt,
        fun,
        arg=None,
        kwarg=None,
        tgt_type="glob",
        batch="50%",
        ret=None,
        *,
        expr_form=None,
    ):
        """
        Run a single command using the ``local_batch`` client

        Wraps :meth:`low`.

        :param expr_form: Deprecated alias for ``tgt_type``
        """
        return self._local_low(
            "local_batch",
            tgt,
            fun,
            arg,
            kwarg,
            tgt_type,
            expr_form,
            batch=batch,
            ret=ret,
        )

    def lookup_jid(self, jid):
        """
        Get job results

        Wraps :meth:`runner`.
        """

        return self.runner("jobs.lookup_jid", jid=f"{jid}")

    def runner(self, fun, arg=None, **kwargs):
        """
        Run a single command using the ``runner`` client

        Usage::
          runner('jobs.lookup_jid', jid=12345)
        """
        low = {
            "client": "runner",
            "fun": fun,
        }
        if arg:
            low["arg"] = arg

        low.update(kwargs)

        return self.low([low])

    def wheel(self, fun, arg=None, kwarg=None, **kwargs):
        """
        Run a single command using the ``wheel`` client

        Usage::
          wheel('key.accept', match='myminion')
        """
        low = {
            "client": "wheel",
            "fun": fun,
        }

        if arg:
            low["arg"] = arg
        if kwarg:
            low["kwarg"] = kwarg

        low.update(kwargs)

        return self.low([low])

    def _send_auth(self, path, **kwargs):
        return self.req(path, kwargs)

    def login(self, username=None, password=None, eauth=None, **kwargs):
        """
        Authenticate with salt-api and return the user permissions and
        authentication token or an empty dict

        """
        local = locals()
        kwargs.update(
            {
                key: local[key]
                for key in ("username", "password", "eauth")
                if local.get(key, None) is not None
            }
        )
        self.auth = self._send_auth("/login", **kwargs).get("return", [{}])[0]
        return self.auth

    def logout(self):
        """
        End the salt-api session and forget its token

        Uses rest_cherrypy's /logout, which ends the session of a token from
        :meth:`login`. It revokes nothing on rest_tornado, which has no /logout,
        or for an eauth token from :meth:`token`, which salt-api answers with
        an authentication error and which stays valid until it expires. The
        token is forgotten either way.
        """
        try:
            return self.req("/logout", {})
        finally:
            self.auth = {}

    def token(self, **kwargs):
        """
        Get an eauth token from Salt for use with the /run URL

        """
        self.auth = self._send_auth("/token", **kwargs)[0]
        return self.auth

    def _construct_url(self, path):
        """
        Construct the url to salt-api for the given path

        Args:
            path: the path to the salt-api resource

        >>> api = Pepper('https://localhost:8000/salt-api/')
        >>> api._construct_url('/login')
        'https://localhost:8000/salt-api/login'
        """

        relative_path = path.lstrip("/")
        return urlparse.urljoin(self.api_url, relative_path)

    def _parse_salt_version(self, version):
        # borrow from salt.version
        git_describe_regex = re.compile(
            r"(?:[^\d]+)?(?P<major>[\d]{1,4})"
            r"\.(?P<minor>[\d]{1,2})"
            r"(?:\.(?P<bugfix>[\d]{0,2}))?"
            r"(?:\.(?P<mbugfix>[\d]{0,2}))?"
            r"(?:(?P<pre_type>rc|a|b|alpha|beta|nb)(?P<pre_num>[\d]{1}))?"
            r"(?:(?:.*)-(?P<noc>(?:[\d]+|n/a))-(?P<sha>[a-z0-9]{8}))?"
        )
        match = git_describe_regex.match(version)
        if match:
            self.salt_version = match.groups()
