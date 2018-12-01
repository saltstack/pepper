#!/bin/bash

set -e

echo "$CODECOV_TOKEN"
tox -c /pepper/tox.ini -e "${CODECOV}${TOXENV}"

if [[ $CODECOV == "py" ]]; then
    tox -c /pepper/tox.ini -e coverage,codecov
fi
