def test_local_poll(pepper_cli, minion_id):
    '''Test the returns poller for localclient'''
    ret = pepper_cli('--run-uri', '--fail-if-incomplete', '*', 'test.sleep', '30')
    assert ret is False
