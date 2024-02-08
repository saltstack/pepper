import json
import pathlib

import pytest


def test_local_bad_opts(pepper_cli):
    with pytest.raises(SystemExit):
        pepper_cli("*")
    with pytest.raises(SystemExit):
        pepper_cli("test.ping")
    with pytest.raises(SystemExit):
        pepper_cli("--client=ssh", "test.ping")
    with pytest.raises(SystemExit):
        pepper_cli("--client=ssh", "*")


@pytest.mark.xfail(
    'config.getoption("--salt-api-backend") == "rest_tornado"',
    reason="timeout kwarg isnt popped until next version of salt/tornado",
)
def test_runner_client(pepper_cli):
    ret = pepper_cli(
        "--timeout=123",
        "--client=runner",
        "test.arg",
        "one",
        "two=what",
        "three={}".format(json.dumps({"hello": "world"})),
    )
    assert ret == {"args": ["one"], "kwargs": {"three": {"hello": "world"}, "two": "what"}}


@pytest.mark.xfail(
    'config.getoption("--salt-api-backend") == "rest_tornado"',
    reason="wheelClient unimplemented for now on tornado",
)
def test_wheel_client_arg(pepper_cli, session_minion):
    ret = pepper_cli("--client=wheel", "minions.connected")
    assert ret == [session_minion.id]


@pytest.mark.xfail(
    'config.getoption("--salt-api-backend") == "rest_tornado"',
    reason="wheelClient unimplemented for now on tornado",
)
def test_wheel_client_kwargs(pepper_cli, session_master):
    ret = pepper_cli(
        "--client=wheel",
        "config.update_config",
        "file_name=pepper",
        "yaml_contents={}".format(json.dumps({"timeout": 5})),
    )
    assert ret == "Wrote pepper.conf"

    default_include_dir = pathlib.Path(session_master.config["default_include"]).parent
    pepper_config = pathlib.Path(session_master.config_dir) / default_include_dir / "pepper.conf"
    assert pepper_config.exists


@pytest.mark.xfail(
    'config.getoption("--salt-api-backend") == "rest_tornado"',
    reason="sshClient unimplemented for now on tornado",
)
def test_ssh_client(pepper_cli, session_ssh_roster_config):
    ret = pepper_cli("--client=ssh", "*", "test.ping")
    assert ret["ssh"]["localhost"]["return"] is True


def test_bad_client(pepper_cli):
    ret = pepper_cli("--client=whatever")
    assert ret == 1
