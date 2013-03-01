======
Pepper
======

Pepper is a collection of CLI scripts that shadow Salt's own CLI scripts but
then proxy those commands through an externally running `salt-api`__ instance.

This allows users to execute Salt commands from computers that are external to
computers running the ``salt-master`` or ``salt-minion`` as though they were
running Salt locally.

.. __: https://github.com/saltstack/salt-api
