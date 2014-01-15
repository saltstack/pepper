'''
A Python library for working with Salt's REST API

(Specifically the rest_cherrypy netapi module.)

'''
import functools
import json
import logging
import os
import urllib
import urllib2
import urlparse

logger = logging.getLogger(__name__)

HEADERS = {
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'X-Requested-With': 'XMLHttpRequest',
}

class Pepper(object):
    '''
    A thin wrapper for making HTTP calls to the salt-api rest_cherrpy REST
    interface

    >>> api = Pepper('http://localhost:8000')
    >>> api.login('saltdev', 'saltdev', 'pam')
    {"return": [
            {
                "eauth": "pam",
                "expire": 1370434219.714091,
                "perms": [
                    "test.*"
                ],
                "start": 1370391019.71409,
                "token": "c02a6f4397b5496ba06b70ae5fd1f2ab75de9237",
                "user": "saltdev"
            }
        ]
    }
    >>> api.cmd([{'client': 'local', 'tgt': '*', 'fun': 'test.ping'}])
    {u'return': [{u'ms-0': True,
              u'ms-1': True,
              u'ms-2': True,
              u'ms-3': True,
              u'ms-4': True}]}

    '''
    def __init__(self, api_url='http://localhost:8000'):
        '''
        Initialize the class with the URL of the API

        :param api_url: Host or IP address of the salt-api URL;
            include the port number

        '''
        self.api_url = api_url
        self.auth = {}

    def req(self, path, data=None):
        '''
        A thin wrapper around urllib2 to send requests and return the response

        Suppresses (and logs) exceptions.

        :rtype: dictionary

        '''
        # Build POST data
        if data != None:
            postdata = json.dumps(data).encode()
            clen = len(postdata)

        # Send request
        url = urlparse.urljoin(self.api_url, path)
        req = urllib2.Request(url, postdata, HEADERS)

        if data != None:
            req.add_header('Content-Length', clen)

        try:
            f = urllib2.urlopen(req)
            ret = json.loads(f.read())
        except (urllib2.HTTPError, urllib2.URLError):
            logger.debug('Error with request', exc_info=True)
            ret = {}
        except AttributeError:
            logger.debug('Error converting response from JSON', exc_info=True)
            ret = {}

        return ret

    def cmd(self, path, lowstate, auth=None):
        '''
        Execute a command through salt-api and return the response

        :param string path: URL path to be joined with the API hostname

        :param list lowstate: a list of lowstate dictionaries

        :param type auth: dictionary or None
        :param auth: authentication credentials to be added to each lowstate
            chunk in the data param; credentials may be passed in directly or
            set on the instance via the login() method

        '''
        return self.req(path, [dict(i, **auth or self.auth) for i in lowstate])

    def run(self, *args, **kwargs):
        '''
        A convenience method for sending requests through the /run URL

        '''
        return self.cmd('/run', *args, **kwargs)

    def login(self, username, password, eauth):
        '''
        Authenticate with salt-api and return the user permissions and
        authentication token

        '''
        # FIXME: this should send a login request and return the auth token for
        # future requests; this first implementation relies on the /run URL and
        # inlining full auth credentials
        auth = {
            'username': username,
            'password': password,
            'eauth': eauth
        }
        self.auth = auth

        # Implementation should look something like:
        # ret = self.req('/login', auth)
        # # If the login succeeded, store the auth token on the instance
        # if 'token' in ret:
        #     self.auth = {'token': ret['token'], 'eauth': ret['eauth']}
        # return {}
