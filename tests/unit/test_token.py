import json
import os
import stat
import sys
import time
from unittest.mock import MagicMock, patch

import pytest

import pepper.cli
from pepper.exceptions import PepperAuthException

PEPPERRC = """
[api1]
SALTAPI_URL=https://api1.example.com/
SALTAPI_USER=pepper
SALTAPI_PASS=pepper
SALTAPI_EAUTH=pam

[api2]
SALTAPI_URL=https://api2.example.com/
SALTAPI_USER=pepper
SALTAPI_PASS=pepper
SALTAPI_EAUTH=pam

[nopass]
SALTAPI_URL=https://api1.example.com/
SALTAPI_USER=pepper
SALTAPI_EAUTH=pam

[nouser]
SALTAPI_URL=https://api1.example.com/
SALTAPI_PASS=pepper
SALTAPI_EAUTH=pam
"""


@pytest.fixture
def cache_file(tmp_path):
    return tmp_path / "peppercache"


@pytest.fixture
def make_cli(tmp_path, cache_file, monkeypatch):
    rcfile = tmp_path / "pepperrc"
    rcfile.write_text(PEPPERRC)

    def _make_cli(profile="api1", *args):
        monkeypatch.setattr(
            sys,
            "argv",
            ["pepper", "-c", str(rcfile), "-p", profile, "-x", str(cache_file), "-T"]
            + list(args)
            + ["*", "test.ping"],
        )
        return pepper.cli.PepperCli()

    return _make_cli


def _api(url, token="new-token", salt_version=None):
    api = MagicMock()
    api.api_url = url
    api.salt_version = salt_version
    api.login = MagicMock(
        return_value={"token": token, "expire": time.time() + 3600, "user": "pepper"}
    )
    return api


def _cached(cache_file):
    return json.loads(cache_file.read_text())


def _tokens(cache_file):
    return sorted(entry["auth"]["token"] for entry in _cached(cache_file).values())


def test_token_is_cached_and_reused(make_cli, cache_file):
    api = _api("https://api1.example.com/")
    assert make_cli().login(api)["token"] == "new-token"
    assert api.login.call_count == 1
    if os.name == "posix":
        assert stat.S_IMODE(cache_file.stat().st_mode) == 0o600

    api = _api("https://api1.example.com/", token="unused")
    assert make_cli().login(api)["token"] == "new-token"
    api.login.assert_not_called()


def test_cached_token_does_not_need_password(make_cli):
    make_cli().login(_api("https://api1.example.com/"))
    api = _api("https://api1.example.com/", token="unused")
    assert make_cli("nopass").login(api)["token"] == "new-token"
    api.login.assert_not_called()


def test_tokens_are_kept_per_url(make_cli, cache_file):
    make_cli("api1").login(_api("https://api1.example.com/", token="token1"))
    make_cli("api2").login(_api("https://api2.example.com/", token="token2"))
    assert _tokens(cache_file) == ["token1", "token2"]

    api = _api("https://api1.example.com/", token="unused")
    assert make_cli("api1").login(api)["token"] == "token1"
    api.login.assert_not_called()


def test_tokens_are_kept_per_user(make_cli, cache_file):
    make_cli("api1").login(_api("https://api1.example.com/", token="token1"))
    api = _api("https://api1.example.com/", token="token2")
    assert make_cli("api1", "--username", "other").login(api)["token"] == "token2"
    assert len(_cached(cache_file)) == 2


def test_expired_token_is_replaced(make_cli, cache_file):
    cli = make_cli()
    api = _api("https://api1.example.com/")
    key = cli._token_cache_key(api, "pepper")
    cache_file.write_text(
        json.dumps({key: {"auth": {"token": "old", "expire": time.time()}}})
    )
    assert cli.login(api)["token"] == "new-token"
    assert _cached(cache_file)[key]["auth"]["token"] == "new-token"


@pytest.mark.parametrize(
    "content",
    [
        json.dumps({"token": "old", "expire": time.time() + 3600}),
        "not json",
        json.dumps(["not", "a", "dict"]),
    ],
    ids=["single-token-format", "invalid-json", "wrong-type"],
)
def test_unusable_cache_file_is_replaced(make_cli, cache_file, content):
    cache_file.write_text(content)
    api = _api("https://api1.example.com/")
    assert make_cli().login(api)["token"] == "new-token"
    assert api.login.call_count == 1
    assert _tokens(cache_file) == ["new-token"]


def test_failed_login_is_not_cached(make_cli, cache_file):
    api = _api("https://api1.example.com/")
    api.login.return_value = {}
    make_cli().login(api)
    assert not cache_file.exists()


def test_rejected_cached_token_logs_in_again(make_cli, cache_file):
    make_cli().login(_api("https://api1.example.com/", token="stale"))

    cli = make_cli()
    api = _api("https://api1.example.com/", token="fresh")
    cli.login(api)
    api.login.assert_not_called()

    calls = []

    def low(*args):
        calls.append(cli.auth["token"])
        if cli.auth["token"] == "stale":
            raise PepperAuthException("Authentication denied")
        return {"return": [{}]}

    assert cli._call(api, low) == {"return": [{}]}
    assert calls == ["stale", "fresh"]
    assert _tokens(cache_file) == ["fresh"]


def test_rejected_fresh_token_is_not_retried(make_cli):
    cli = make_cli()
    api = _api("https://api1.example.com/")
    cli.login(api)
    low = MagicMock(side_effect=PepperAuthException("Authentication denied"))
    with pytest.raises(PepperAuthException):
        cli._call(api, low)
    assert low.call_count == 1
    assert api.login.call_count == 1


def test_rejected_cached_token_without_credentials(make_cli, cache_file):
    make_cli().login(_api("https://api1.example.com/", token="valid"))

    cli = make_cli("nopass", "--non-interactive")
    api = _api("https://api1.example.com/", token="unused")
    cli.login(api)
    low = MagicMock(side_effect=PepperAuthException("Authentication denied: no"))
    with pytest.raises(PepperAuthException, match="Authentication denied: no"):
        cli._call(api, low)
    # Without credentials to log in with, the rejected token is dropped so the
    # next run does not offer it again
    assert _cached(cache_file) == {}
    api.login.assert_not_called()


def test_run_uri_tokens_are_kept_apart(make_cli, cache_file):
    make_cli().login(_api("https://api1.example.com/", token="session"))
    api = _api("https://api1.example.com/")
    api.token = MagicMock(return_value={"token": "eauth", "expire": time.time() + 3600})
    assert make_cli("api1", "--run-uri").login(api)["token"] == "eauth"
    assert _tokens(cache_file) == ["eauth", "session"]

    api = _api("https://api1.example.com/", token="unused")
    assert make_cli().login(api)["token"] == "session"
    api.login.assert_not_called()


@pytest.mark.parametrize("expire", ["soon", None, [1]], ids=["string", "null", "list"])
def test_non_numeric_expire(make_cli, cache_file, expire):
    cli = make_cli()
    api = _api("https://api1.example.com/")
    other = json.dumps(["https://api2.example.com/", "pepper", "pam", "login"])
    cache_file.write_text(
        json.dumps({other: {"auth": {"token": "odd", "expire": expire}}})
    )
    assert cli.login(api)["token"] == "new-token"
    assert _tokens(cache_file) == ["new-token"]

    api = _api("https://api1.example.com/")
    api.login.return_value = {"token": "odd", "expire": expire}
    make_cli().login(api)


def test_permission_error_keeps_new_token(make_cli, cache_file):
    make_cli().login(_api("https://api1.example.com/", token="cached"))

    cli = make_cli()
    api = _api("https://api1.example.com/", token="fresh")
    cli.login(api)
    low = MagicMock(side_effect=PepperAuthException("Authentication denied: no"))
    with pytest.raises(PepperAuthException):
        cli._call(api, low)
    assert low.call_count == 2
    assert _tokens(cache_file) == ["fresh"]


def test_prompted_user_is_part_of_the_key(make_cli, cache_file):
    with patch("pepper.cli.input", MagicMock(return_value="alice")):
        make_cli("nouser").login(_api("https://api1.example.com/", token="alice"))
    with patch("pepper.cli.input", MagicMock(return_value="bob")) as prompt:
        api = _api("https://api1.example.com/", token="bob")
        assert make_cli("nouser").login(api)["token"] == "bob"
    prompt.assert_called_once()
    assert api.login.call_args.kwargs["username"] == "bob"
    assert _tokens(cache_file) == ["alice", "bob"]


def test_cached_token_restores_salt_version(make_cli):
    version = ("3006", "30", None, None, None, None, None, None)
    make_cli().login(_api("https://api1.example.com/", salt_version=version))
    api = _api("https://api1.example.com/", token="unused")
    make_cli().login(api)
    api.login.assert_not_called()
    assert api.salt_version == version
