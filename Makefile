PYTHON_VERSION?=py37

test:
	pip install tox
	tox -e flake8,$(PYTHON_VERSION)-$(BACKEND)-$(SALT)
