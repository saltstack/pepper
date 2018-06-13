def test_local(pepper_cli, minion_id):
    '''Sanity-check: Has at least one minion'''
    ret = pepper_cli('*', 'test.ping')
    assert ret is False

def test_run(pepper_cli, minion_id):
    '''Run command via /run URI'''
    ret = pepper_cli('--run-uri', '*', 'test.ping')
    assert ret is False

def test_long_local(pepper_cli, minion_id):
    '''Test a long call blocks until the return'''
    ret = pepper_cli('*', 'test.sleep', '30')
    assert ret is False
