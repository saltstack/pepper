def test_local(pepper_client, minion_id):
    assert pepper_client.local('*', 'test.ping')['return'][0][minion_id] is True
