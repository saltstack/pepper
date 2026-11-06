======
Pepper
======

.. image:: https://img.shields.io/pypi/v/salt-pepper.svg
   :target: https://pypi.org/project/salt-pepper
.. image:: https://github.com/saltstack/pepper/actions/workflows/test.yaml/badge.svg?branch=develop
   :target: https://github.com/saltstack/pepper/actions/workflows/test.yaml
.. image:: https://img.shields.io/pypi/pyversions/salt-pepper.svg
   :target: https://pypi.org/project/salt-pepper
.. image:: https://img.shields.io/badge/license-Apache2-blue.svg?maxAge=3600
   :target: https://pypi.org/project/salt-pepper

Pepper contains a Python library and CLI scripts for accessing a remote
`salt-api`__ instance.

``pepperlib`` abstracts the HTTP calls to ``salt-api`` so existing Python
projects can easily integrate with a remote Salt installation just by
instantiating a class.

The ``pepper`` CLI script allows users to execute Salt commands from computers
that are external to computers running the ``salt-master`` or ``salt-minion``
daemons as though they were running Salt locally. The long-term goal is to add
additional CLI scripts maintain the same interface as Salt's own CLI scripts
(``salt``, ``salt-run``, ``salt-key``, etc).

It runs on Python 3.10 or later, and the CLI only needs the standard library.
When ``salt`` is installed in the same environment, pepper formats results with
Salt's outputters.

.. __: https://docs.saltproject.io/en/latest/ref/netapi/all/index.html

Installation
------------
.. code-block:: bash

    pip install salt-pepper

Kerberos logins and the library's ``req_get()`` and ``req_stream()`` methods
need ``requests``, which is available as an extra:

.. code-block:: bash

    pip install 'salt-pepper[kerberos]'
    pip install 'salt-pepper[requests]'

Usage
-----

Installing the package provides a ``pepper`` command (``pepper.exe`` on
Windows), which can also be run as ``python -m pepper``.

.. code-block:: bash

    export SALTAPI_USER=saltdev SALTAPI_PASS=saltdev SALTAPI_EAUTH=pam
    pepper '*' test.ping
    pepper '*' test.kwarg hello=dolly

``cmd.exe`` on Windows does not treat single quotes as quoting, so
``pepper '*' test.ping`` targets the literal string ``'*'``. ``cmd.exe`` does
not expand wildcards either, so leave the target unquoted there:
``pepper * test.ping``.

Like ``salt``, pepper exits with 1 when any minion returns a non-zero retcode
or does not respond, and with 2 when the target matches no minions, and like
``salt-run`` it exits with the job's retcode when a runner fails. The
``--fail-any``, ``--fail-any-none``, ``--fail-all`` and ``--fail-all-none``
options replace that rule; see ``pepper --help``. salt-api does not return
minion retcodes with ``--batch``, or for the local client with ``rest_tornado``,
and the ``--fail-if-incomplete`` poller reads results without them, so in those
cases pepper cannot tell that a minion failed. For the same reason
``--fail-if-incomplete`` cannot be combined with the ``--fail-*`` options.

``-t``/``--timeout`` works like ``salt -t``: salt-api waits that long for
minions to return, but keeps waiting for minions that are still running the
job. To stop sooner, add ``--fail-if-incomplete``, which polls for returns every
few seconds, stops polling once ``--timeout`` has passed and reports the minions
that did not return. It does not cut short a poll that is in progress, and
pepper sets no timeout on its requests to salt-api, so the command can still
run past ``--timeout`` when salt-api is slow to answer. The job keeps running on
the minions that did not return either way.

.. code-block:: bash

    pepper --fail-if-incomplete -t 30 '*' cmd.run 'sleep 300'

When salt is installed, results are shown with Salt's outputters, and
``--out``, ``--state-output``, ``--state-verbose``, ``--no-color`` and
``--force-color`` work as they do with ``salt``. Output written with
``--output-file`` is not colored unless ``--force-color`` is given.

.. code-block:: bash

    pepper --state-output=changes --state-verbose=false '*' state.apply

Examples leveraging the runner client.

.. code-block:: bash

    pepper --client runner reactor.list
    pepper --client runner reactor.add event='test/provision/*' reactors='/srv/salt/state/reactor/test-provision.sls'

Library
-------

.. code-block:: python

    from pepper import Pepper

    api = Pepper("https://salt.example.com:8000")
    api.login("saltdev", "saltdev", "pam")
    api.local("*", "test.ping")
    api.local("G@os:Debian", "pkg.version", ["openssl"], tgt_type="compound")
    api.runner("jobs.lookup_jid", jid="20261105120000000000")
    api.logout()

``local(..., full_return=True)`` returns each minion's retcode along with its
result, as the CLI asks for.

``logout()`` ends the rest_cherrypy session of a token from ``login()``. It
revokes nothing on rest_tornado, which has no ``/logout``, or for an eauth
token from ``token()`` (``--run-uri``): salt-api answers with an authentication
error, and the token stays valid until it expires.

``Pepper.from_config()`` creates a client from a ``.pepperrc`` profile and the
``SALTAPI_*`` environment variables, the same way the ``pepper`` command does,
and logs in. The environment variables are used as the command uses them
(see Configuration); pass ``environment=True`` to let them override any
profile, or ``environment=False`` to ignore them. A config file or profile that
was named, by argument or by ``PEPPERRC`` or ``PEPPERPROFILE``, and cannot be
found raises an error instead of falling back to the defaults:

.. code-block:: python

    from pepper import Pepper

    api = Pepper.from_config(profile="main")
    api.local("*", "test.ping")

Configuration
-------------

You can configure pepper through the command line, using environment variables
or in a configuration file ``$HOME/.pepperrc`` with the following syntax :

.. code-block::

  [main]
  SALTAPI_URL=https://localhost:8000/
  SALTAPI_USER=saltdev
  SALTAPI_PASS=saltdev
  SALTAPI_EAUTH=pam

Command line options override both. ``SALTAPI_*`` environment variables
override the default profile, but a profile named with ``-p`` or
``PEPPERPROFILE`` keeps its own settings: the environment variables only fill in
the ones it does not set, so a ``SALTAPI_URL`` exported in the shell cannot
send that profile's credentials to another salt-api.

Tokens
------

``-T`` (``--make-token``) saves the salt-api token in ``~/.peppercache`` (or
the file given with ``-x`` or ``PEPPERCACHE``) and reuses it until it expires,
so the password is only needed when a new token has to be requested. The file
holds one token for each salt-api URL, user, eauth and token type (``-r``
uses its own). If salt-api rejects a cached token, for example after a
restart, pepper logs in again once and replaces it. If it cannot log in again,
it removes the rejected token from the file.

Output
------

When salt is installed, pepper reads Salt outputter settings from a Salt
configuration file, ``~/.config/pepper/master`` by default (``-m`` or
``MASTER_CONFIG`` to change it). As with the ``salt`` command, settings in
``~/.saltrc``, or in ``$XDG_CONFIG_HOME/salt/saltrc`` (``~/.config/salt/saltrc``)
when that directory exists, or in the file named by ``SALT_CLIENT_CONFIG``,
override that file. Command line options take precedence:

.. code-block:: yaml

  output: json
  state_output: changes
  state_verbose: false

TLS
---

Pepper verifies the salt-api TLS certificate against the system's trusted CA
certificates. ``--ignore-ssl-errors`` turns verification off, which should only
be used for testing.

Python 3.13 and later verify certificates with ``VERIFY_X509_STRICT``, which
rejects a CA certificate without the keyUsage extension ("CA cert does not
include key usage extension"). CA certificates made with ``openssl req -x509``
and its default configuration lack it. Reissue the CA certificate with
``keyUsage = critical, keyCertSign, cRLSign``.

To verify against a private CA, or to present a client certificate, use the
command line options or set them in ``.pepperrc`` or the environment:

.. code-block::

  [main]
  SALTAPI_URL=https://salt.example.com:8000/
  SALTAPI_CA_BUNDLE=/path/to/ca-chain.pem
  SALTAPI_CLIENT_CERT=/path/to/client.pem
  SALTAPI_CLIENT_CERT_KEY=/path/to/client.key

``SALTAPI_CA_BUNDLE`` (``--ca-bundle``) replaces the system CA certificates
rather than adding to them. Kerberos logins and the library methods that use
``requests`` verify against requests' own CA bundle (certifi) unless
``SALTAPI_CA_BUNDLE`` is set. ``SALTAPI_CLIENT_CERT_KEY``
(``--client-cert-key``) can be left out when the client certificate file also
contains the private key.

A private CA certificate that Python 3.13 rejects for lacking keyUsage can also
be worked around by passing the salt-api server certificate itself as
``--ca-bundle``.

Pepper uses these settings when salt-api redirects it from HTTP to HTTPS. It
refuses to follow a redirect from HTTPS to HTTP, and does not send the salt-api
token on when a redirect goes to another host or port.

Contributing
------------

Pull requests are welcome. This repo follows the same `contributing
guidelines`__ as Salt. Open pull requests against the ``develop`` branch.

The pre-commit hooks run the same formatters and linters as Salt (black,
isort, pyupgrade, bandit and pylint):

.. code-block:: bash

    pip install pre-commit
    pre-commit install

Changes that affect users need a changelog fragment in the ``changelog/``
directory, named ``<issue number>.<type>.md``, where the type is one of
``removed``, ``deprecated``, ``changed``, ``fixed``, ``added`` or
``security``:

.. code-block:: bash

    echo "Fixed the exit code when a runner job fails" > changelog/195.fixed.md

The test suite starts a salt-master, salt-minion and salt-api, and runs under
nox:

.. code-block:: bash

    pip install nox
    nox -e tests

.. __: https://docs.saltproject.io/en/latest/topics/development/contributing.html

Releasing
---------

The ``release`` workflow builds the sdist and wheel and publishes them to PyPI
when a GitHub release is published. It uses PyPI `trusted publishing`_, which
has to be set up once on PyPI for the ``salt-pepper`` project with this
repository, the ``release.yaml`` workflow and the ``release`` environment.

To make a release:

1. Collect the changelog fragments into ``CHANGELOG.md`` and commit the result
   to ``develop``:

   .. code-block:: bash

       pip install towncrier
       towncrier build --yes --version 0.8.0

2. Publish a GitHub release with a new tag named after the version, for
   example ``0.8.0``. The version is read from the tag.

.. _trusted publishing: https://docs.pypi.org/trusted-publishers/adding-a-publisher/
