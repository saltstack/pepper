import pytest

TORNADO_NO_RETCODES = pytest.mark.xfail(
    'config.getoption("--salt-api-backend") == "rest_tornado"',
    reason="rest_tornado does not return minion retcodes for the local client",
)


def test_success_exit_code(pepper_cli, session_minion_id):
    ret = pepper_cli("*", "test.ping")
    assert ret[session_minion_id] is True
    assert pepper_cli.exitcode == 0


@TORNADO_NO_RETCODES
def test_minion_failure_exit_code(pepper_cli, session_minion_id):
    pepper_cli("*", "cmd.run", "exit 3")
    assert pepper_cli.exitcode == 1


@TORNADO_NO_RETCODES
def test_fail_any_exit_code(pepper_cli, session_minion_id):
    pepper_cli("--fail-any", "*", "cmd.run", "exit 3")
    assert pepper_cli.exitcode == 3
