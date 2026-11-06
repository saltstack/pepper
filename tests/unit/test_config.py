import sys

import pepper.cli

PEPPERRC = """
[main]
SALTAPI_URL=https://main.example.com/
SALTAPI_USER=main-user

[other]
SALTAPI_URL=https://other.example.com/
"""


def _cli(tmp_path, monkeypatch, *args):
    rcfile = tmp_path / "pepperrc"
    rcfile.write_text(PEPPERRC)
    monkeypatch.setattr(sys, "argv", ["pepper", "-c", str(rcfile), *args])
    return pepper.cli.PepperCli()


def test_get_config_reads_selected_profile(tmp_path, monkeypatch):
    cli = _cli(tmp_path, monkeypatch, "-p", "other")
    assert cli.get_config({"SALTAPI_URL": None, "SALTAPI_USER": "default"}) == {
        "SALTAPI_URL": "https://other.example.com/",
        "SALTAPI_USER": "default",
    }


def test_get_config_missing_profile_uses_defaults(tmp_path, monkeypatch):
    cli = _cli(tmp_path, monkeypatch, "-p", "missing")
    assert cli.get_config({"SALTAPI_URL": "https://localhost:8000/"}) == {
        "SALTAPI_URL": "https://localhost:8000/"
    }


def test_get_config_environment_overrides_file(tmp_path, monkeypatch):
    monkeypatch.setenv("SALTAPI_USER", "env-user")
    cli = _cli(tmp_path, monkeypatch)
    assert cli.get_config({"SALTAPI_USER": None}) == {"SALTAPI_USER": "env-user"}


def test_parse_url_precedence(tmp_path, monkeypatch):
    assert _cli(tmp_path, monkeypatch).parse_url() == "https://main.example.com/"
    monkeypatch.setenv("SALTAPI_URL", "https://env.example.com/")
    assert _cli(tmp_path, monkeypatch).parse_url() == "https://env.example.com/"
    cli = _cli(tmp_path, monkeypatch, "-u", "https://cli.example.com/")
    assert cli.parse_url() == "https://cli.example.com/"
