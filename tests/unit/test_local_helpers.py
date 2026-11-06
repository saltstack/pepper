from unittest.mock import patch

import pytest

from pepper.exceptions import PepperException
from pepper.libpepper import Pepper


@pytest.fixture
def sent():
    """
    The low data each helper passes to Pepper.low()
    """
    with patch.object(Pepper, "low", autospec=True) as low:
        yield lambda: low.call_args.args[1]


@pytest.mark.parametrize("client", ["local", "local_async", "local_batch"])
def test_tgt_type(sent, client):
    getattr(Pepper(), client)("G@os:Debian", "test.ping", tgt_type="compound")
    (low,) = sent()
    assert low["client"] == client
    assert low["tgt_type"] == "compound"
    assert "expr_form" not in low
    assert "full_return" not in low


@pytest.mark.parametrize("client", ["local", "local_async", "local_batch"])
def test_tgt_type_defaults_to_glob(sent, client):
    getattr(Pepper(), client)("*", "test.ping")
    assert sent()[0]["tgt_type"] == "glob"


def test_tgt_type_positional(sent):
    Pepper().local("web1,web2", "test.ping", None, None, "list")
    assert sent()[0]["tgt_type"] == "list"


@pytest.mark.parametrize("client", ["local", "local_async", "local_batch"])
def test_expr_form_is_a_deprecated_alias(sent, client):
    with pytest.warns(DeprecationWarning, match="tgt_type"):
        getattr(Pepper(), client)("web*", "test.ping", expr_form="pcre")
    (low,) = sent()
    assert low["tgt_type"] == "pcre"
    assert "expr_form" not in low


def test_full_return(sent):
    Pepper().local("*", "test.ping", full_return=True)
    assert sent()[0]["full_return"] is True


def test_local_options(sent):
    Pepper().local(
        "*", "test.arg", ["a"], {"b": 1}, timeout=5, ret="smtp", full_return=True
    )
    assert sent() == [
        {
            "client": "local",
            "tgt": "*",
            "fun": "test.arg",
            "arg": ["a"],
            "kwarg": {"b": 1},
            "tgt_type": "glob",
            "full_return": True,
            "timeout": 5,
            "ret": "smtp",
        }
    ]


def test_local_batch_size(sent):
    Pepper().local_batch("*", "test.ping", batch="10")
    assert sent()[0]["batch"] == "10"


def test_logout_forgets_token():
    api = Pepper()
    api.auth = {"token": "abc"}
    with patch.object(
        Pepper, "req", autospec=True, return_value={"return": "ok"}
    ) as req:
        assert api.logout() == {"return": "ok"}
    assert req.call_args.args[1:] == ("/logout", {})
    assert api.auth == {}


def test_logout_forgets_token_on_error():
    api = Pepper()
    api.auth = {"token": "abc"}
    with patch.object(Pepper, "req", autospec=True, side_effect=PepperException("x")):
        with pytest.raises(PepperException):
            api.logout()
    assert api.auth == {}
