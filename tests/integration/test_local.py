def test_local(pepper_client, session_minion_id):
    assert pepper_client.local('*', 'test.ping')['return'][0][session_minion_id] is True
