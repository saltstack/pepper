from unittest.mock import patch

import pytest

from pepper.exceptions import PepperAuthException, PepperException
from pepper.libpepper import Pepper

PEPPERRC = """
[main]
SALTAPI_URL=https://main.example.com/
SALTAPI_USER=pepper
SALTAPI_PASS=secret
SALTAPI_EAUTH=pam

[tls]
SALTAPI_URL=https://tls.example.com/
SALTAPI_USER=pepper
SALTAPI_PASS=secret
SALTAPI_CA_BUNDLE=/etc/ssl/ca.pem
SALTAPI_CLIENT_CERT=/etc/ssl/client.pem

[kerberos]
SALTAPI_URL=https://krb.example.com/
SALTAPI_USER=pepper
SALTAPI_EAUTH=kerberos

[nopass]
SALTAPI_URL=https://main.example.com/
SALTAPI_USER=pepper
"""


@pytest.fixture
def rcfile(tmp_path):
    path = tmp_path / "pepperrc"
    path.write_text(PEPPERRC)
    return str(path)


@pytest.fixture
def login():
    with patch.object(Pepper, "login", autospec=True) as login:
        yield login


def test_from_config(rcfile, login):
    api = Pepper.from_config(path=rcfile)
    assert api.api_url == "https://main.example.com/"
    login.assert_called_once_with(api, "pepper", "secret", "pam")


def test_from_config_profile_and_tls(rcfile, login):
    api = Pepper.from_config(profile="tls", path=rcfile, login=False)
    assert api.api_url == "https://tls.example.com/"
    assert api._ca_bundle == "/etc/ssl/ca.pem"
    assert api._client_cert == "/etc/ssl/client.pem"
    login.assert_not_called()


def test_from_config_environment(rcfile, login, monkeypatch):
    monkeypatch.setenv("PEPPERRC", rcfile)
    monkeypatch.setenv("PEPPERPROFILE", "tls")
    monkeypatch.setenv("SALTAPI_PASS", "from-env")
    api = Pepper.from_config()
    assert api.api_url == "https://tls.example.com/"
    login.assert_called_once_with(api, "pepper", "from-env", "auto")


def test_from_config_kwargs_win(rcfile, login):
    api = Pepper.from_config(
        profile="tls", path=rcfile, ca_bundle="/other.pem", ignore_ssl_errors=True
    )
    assert api._ca_bundle == "/other.pem"
    assert api._ssl_verify is False


def test_from_config_kerberos(rcfile, login):
    api = Pepper.from_config(profile="kerberos", path=rcfile)
    login.assert_called_once_with(api, "pepper", None, "kerberos")


def test_from_config_missing_password(rcfile, login):
    with pytest.raises(PepperAuthException, match="SALTAPI_PASS"):
        Pepper.from_config(profile="nopass", path=rcfile)
    assert Pepper.from_config(profile="nopass", path=rcfile, login=False)


def test_from_config_without_environment(rcfile, login, monkeypatch):
    monkeypatch.setenv("SALTAPI_URL", "https://prod.example.com/")
    monkeypatch.setenv("SALTAPI_PASS", "from-env")
    api = Pepper.from_config(profile="tls", path=rcfile, environment=False)
    assert api.api_url == "https://tls.example.com/"
    login.assert_called_once_with(api, "pepper", "secret", "auto")


def test_from_config_named_profile_ignores_environment(rcfile, login, monkeypatch):
    monkeypatch.setenv("SALTAPI_URL", "https://other.example.com/")
    monkeypatch.setenv("SALTAPI_USER", "other")
    api = Pepper.from_config(profile="tls", path=rcfile)
    assert api.api_url == "https://tls.example.com/"
    login.assert_called_once_with(api, "pepper", "secret", "auto")


def test_from_config_named_profile_with_environment(rcfile, login, monkeypatch):
    monkeypatch.setenv("SALTAPI_URL", "https://other.example.com/")
    api = Pepper.from_config(profile="tls", path=rcfile, environment=True)
    assert api.api_url == "https://other.example.com/"


def test_from_config_missing_file(tmp_path, login):
    missing = str(tmp_path / "missing")
    with pytest.raises(PepperException, match="Unable to read the pepper config"):
        Pepper.from_config(path=missing)
    login.assert_not_called()


def test_from_config_missing_file_from_environment(tmp_path, login, monkeypatch):
    monkeypatch.setenv("PEPPERRC", str(tmp_path / "missing"))
    with pytest.raises(PepperException, match="Unable to read the pepper config"):
        Pepper.from_config()


@pytest.mark.parametrize("from_env", [False, True], ids=["argument", "environment"])
def test_from_config_missing_profile(rcfile, login, monkeypatch, from_env):
    if from_env:
        monkeypatch.setenv("PEPPERPROFILE", "prdo")
        kwargs = {}
    else:
        kwargs = {"profile": "prdo"}
    with pytest.raises(PepperException, match="Profile prdo not found"):
        Pepper.from_config(path=rcfile, **kwargs)
    login.assert_not_called()


def test_from_config_environment_only(tmp_path, login, monkeypatch):
    # Without a config file, the default profile comes from the environment
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SALTAPI_URL", "https://env.example.com/")
    monkeypatch.setenv("SALTAPI_USER", "pepper")
    monkeypatch.setenv("SALTAPI_PASS", "secret")
    api = Pepper.from_config()
    assert api.api_url == "https://env.example.com/"
    login.assert_called_once_with(api, "pepper", "secret", "auto")
