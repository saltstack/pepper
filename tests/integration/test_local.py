import pytest


def test_local(pepper_client, session_minion_id):
    assert pepper_client.local("*", "test.ping")["return"][0][session_minion_id] is True


def test_local_tgt_type(pepper_client, session_minion_id):
    ret = pepper_client.local([session_minion_id], "test.ping", tgt_type="list")
    assert ret["return"][0][session_minion_id] is True


@pytest.mark.xfail(
    'config.getoption("--salt-api-backend") == "rest_tornado"',
    reason="rest_tornado ignores full_return for the local client",
)
def test_local_full_return(pepper_client, session_minion_id):
    ret = pepper_client.local("*", "test.ping", full_return=True)
    assert ret["return"][0][session_minion_id]["ret"] is True
    assert ret["return"][0][session_minion_id]["retcode"] == 0
