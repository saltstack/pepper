======
Pepper
======

Pepper is a collection of CLI scripts that shadow Salt's own CLI scripts but
then proxy those commands through an externally running `salt-api`__ instance.

This allows users to execute Salt commands from computers that are external to
computers running the ``salt-master`` or ``salt-minion`` as though they were
running Salt locally.

Usage
-----

Basic usage is in heavy flux.

.. code-block:: bash

    SALTAPI_USER=saltdev SALTAPI_PASS=saltdev SALTAPI_EAUTH=pam salt '*' test.ping
    SALTAPI_USER=saltdev SALTAPI_PASS=saltdev SALTAPI_EAUTH=pam salt '*' test.kwarg hello=dolly

Current status
--------------

The project is currently pre-alpha.

Follow progress by watching the project issues and milestones. We'll tag and
upload a release to PyPI once the project is ready for a first release.

Please feel free to get involved by sending pull requests or join us on the
Salt mailing list or on IRC in #salt or #salt-devel.

.. __: https://github.com/saltstack/salt-api
