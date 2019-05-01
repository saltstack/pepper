PYVERSION?=py37
SALT?=v2019.2
BACKEND?=cherrypy
DEBIAN_FRONTEND=noninteractive

test:
	apt update && apt install -y libc6-dev libffi-dev gcc git openssh-server libzmq3-dev
	pip install tox
	tox -e flake8,$(PYVERSION)-$(BACKEND)-$(SALT)
