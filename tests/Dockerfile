ARG  PY_VER=latest
ARG  IMG_VARIANT=
FROM python:${PY_VER}${IMG_VARIANT}

RUN set -ex &&\
    OS="$(grep '^ID=' /etc/os-release | sed 's/ID=\(.*\)/\1/')" &&\
    if [ "${OS}" = 'debian' ]; then \
      apt-get -qq update &&\
      DEBIAN_FRONTEND=noninteractive apt-get -yqq --no-install-suggests --no-install-recommends install \
        libc6-dev libffi-dev gcc git \
        openssh-server libzmq3-dev \
	> /dev/null &&\
      rm -rf -- /var/lib/apt/lists/* /var/cache/apt/* ;\
    elif [ "${OS}" = 'alpine' ]; then \
      apk add --no-cache libc-dev libffi-dev gcc git \
        openssh openssl-dev which zeromq-dev \
        > /dev/null ;\
    else \
      exit 1 ;\
    fi &&\
    pip --quiet --no-cache-dir install tox

CMD ["tox"]
