#!/usr/bin/env python
'''
These integration tests will execute non-destructive commands against a real
Salt and salt-api instance. Those must be set up and started independently.
This will take several minutes to run.

Usage:

SALTAPI_URL=http://localhost:8000 \
SALTAPI_USER=saltdev \
SALTAPI_PASS=saltdev \
SALTAPI_EAUTH=auto \
    python -m unittest tests.integration
'''
import itertools
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest

try:
    SALTAPI_URL = os.environ['SALTAPI_URL']
    SALTAPI_USER = os.environ['SALTAPI_USER']
    SALTAPI_PASS = os.environ['SALTAPI_PASS']
    SALTAPI_EAUTH = os.environ['SALTAPI_EAUTH']
except KeyError:
    raise SystemExit('The following environment variables must be set: '
                     'SALTAPI_URL, SALTAPI_USER, SALTAPI_PASS, SALTAPI_EAUTH.')


def _pepper(*args):
    '''
    Wrapper to invoke Pepper with common params and inside an empty env
    '''
    def_args = [
        'pepper',
        '--saltapi-url={0}'.format(SALTAPI_URL),
        '--username={0}'.format(SALTAPI_USER),
        '--password={0}'.format(SALTAPI_PASS),
        '--eauth={0}'.format(SALTAPI_EAUTH),
    ]

    return subprocess.check_output(itertools.chain(def_args, args))


class TestVanilla(unittest.TestCase):
    def _pepper(self, *args):
        return json.loads(_pepper(*args))['return'][0]

    def test_local(self):
        '''Sanity-check: Has at least one minion'''
        ret = self._pepper('*', 'test.ping')
        self.assertTrue(ret.values()[0])

    def test_run(self):
        '''Run command via /run URI'''
        ret = self._pepper('--run-uri', '*', 'test.ping')
        self.assertTrue(ret.values()[0])

    def test_long_local(self):
        '''Test a long call blocks until the return'''
        ret = self._pepper('*', 'test.sleep', '30')
        self.assertTrue(ret.values()[0])


class TestPoller(unittest.TestCase):
    def _pepper(self, *args):
        return _pepper(*args).splitlines()[0]

    def test_local_poll(self):
        '''Test the returns poller for localclient'''
        ret = self._pepper('--run-uri', '--fail-if-incomplete', '*', 'test.sleep', '30')
        self.assertTrue('True' in ret)


class TestTokens(unittest.TestCase):
    def setUp(self):
        self.tokdir = tempfile.mkdtemp()
        self.tokfile = os.path.join(self.tokdir, 'peppertok.json')

    def tearDown(self):
        shutil.rmtree(self.tokdir)

    def _pepper(self, *args):
        return json.loads(_pepper(*args))['return'][0]

    def test_local_token(self):
        '''Test local execution with token file'''
        ret = self._pepper('-x', self.tokfile,
                           '--make-token', '--run-uri', '*', 'test.ping')
        self.assertTrue(ret.values()[0])

    def test_runner_token(self):
        '''Test runner execution with token file'''
        ret = self._pepper('-x', self.tokfile,
                           '--make-token', '--run-uri',
                           '--client', 'runner', 'test.metasyntactic')
        self.assertTrue(ret[0] == 'foo')

    def test_token_expire(self):
        '''Test token override param'''
        now = time.time()
        self._pepper('-x', self.tokfile, '--make-token', '--run-uri',
                     '--token-expire', '94670856',
                     '*', 'test.ping')

        with open(self.tokfile, 'r') as f:
            token = json.load(f)
            diff = (now + float(94670856)) - token['expire']
            # Allow for 10-second window between request and master-side auth.
            self.assertTrue(diff < 10)
