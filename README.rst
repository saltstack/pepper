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

It does not require any additional dependencies and runs on Python 2.5+ and
Python 3. (Python 3 support is new, please file an issue if you encounter
trouble.)

.. __: https://github.com/saltstack/salt-api

Installation
------------
.. code-block:: bash

    pip install salt-pepper

Usage
-----

Basic usage is in heavy flux. You can run pepper using the script in %PYTHONHOME%/scripts/pepper (a pepper.cmd wrapper is provided for convenience to Windows users).

.. code-block:: bash

    export SALTAPI_USER=saltdev SALTAPI_PASS=saltdev SALTAPI_EAUTH=pam
    pepper '*' test.ping
    pepper '*' test.kwarg hello=dolly

Examples leveraging the runner client.

.. code-block:: bash

    pepper --client runner reactor.list
    pepper --client runner reactor.add event='test/provision/*' reactors='/srv/salt/state/reactor/test-provision.sls'

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
