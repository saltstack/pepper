======
Pepper
======

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

.. __: https://github.com/saltstack/salt-api

Usage
-----

Basic usage is in heavy flux.

.. code-block:: bash

    SALTAPI_USER=saltdev SALTAPI_PASS=saltdev SALTAPI_EAUTH=pam pepper '*' test.ping
    SALTAPI_USER=saltdev SALTAPI_PASS=saltdev SALTAPI_EAUTH=pam pepper '*' test.kwarg hello=dolly

Current status
--------------

The project is currently pre-alpha.

Follow progress by `watching the project milestones`__. We'll tag and upload a
release to PyPI once the project is ready for a first release.

Please feel free to get involved by sending pull requests or join us on the
Salt mailing list or on IRC in #salt or #salt-devel.

.. __: https://github.com/saltstack/pepper/issues/milestones
