'''
A Python library for working with Salt's REST API

(Specifically the rest_cherrypy netapi module.)

'''
import json
import logging
import requests
import urlparse

logger = logging.getLogger('pepper')


class PepperException(Exception):
    pass


class Pepper(object):
    '''
    A thin wrapper for making HTTP calls to the salt-api rest_cherrpy REST
    interface

    >>> api = Pepper('https://localhost:8000')
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
    >>> api.low([{'client': 'local', 'tgt': '*', 'fun': 'test.ping'}])
    {u'return': [{u'ms-0': True,
              u'ms-1': True,
              u'ms-2': True,
              u'ms-3': True,
              u'ms-4': True}]}

    '''
    def __init__(self, api_url='https://localhost:8000', debug_http=False,
                 ssl_verify=True):
        '''
        Initialize the class with the URL of the API

        :param api_url: Host or IP address of the salt-api URL;
            include the port number

        :param debug_http: Add a flag to urllib2 to output the HTTP exchange

        :raises PepperException: if the api_url is misformed

        '''
        split = urlparse.urlsplit(api_url)
        if split.scheme not in ['http', 'https']:
            raise PepperException("salt-api URL missing HTTP(s) protocol: {0}"
                                  .format(self.api_url))

        self.api_url = api_url
        self.debug_http = int(debug_http)
        self.auth = {}
        self._ssl_verify = ssl_verify

    def req(self, path, data=None):
        '''
        A thin wrapper around urllib2 to send requests and return the response

        If the current instance contains an authentication token it will be
        attached to the request as a custom header.

        :rtype: dictionary

        '''
        auth = None
        if (hasattr(data, 'get') and data.get('eauth') == 'kerberos') \
                or self.auth.get('eauth') == 'kerberos':
            from requests_kerberos import HTTPKerberosAuth, OPTIONAL
            auth = HTTPKerberosAuth(mutual_authentication=OPTIONAL)

        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
        }
        # Add auth header to request
        if self.auth and 'token' in self.auth and self.auth['token']:
            headers['X-Auth-Token'] = self.auth['token']
        params = {'url': self._construct_url(path),
                  'headers': headers,
                  'verify': self._ssl_verify,
                  'auth': auth,
                  'data': json.dumps(data),
                  }

        if not self._ssl_verify:
            requests.packages.urllib3.disable_warnings()

        logger.debug('postdata {0}'.format(params))
        resp = requests.post(**params)
        if resp.status_code == 401:
            # TODO should be resp.raise_from_status
            raise PepperException('Authentication denied')
        if resp.status_code == 500:
            # TODO should be resp.raise_from_status
            raise PepperException('Server error.')
        return resp.json()

    def low(self, lowstate, path='/'):
        '''
        Execute a command through salt-api and return the response

        :param string path: URL path to be joined with the API hostname

        :param list lowstate: a list of lowstate dictionaries
        '''
        return self.req(path, lowstate)

    def local(self, tgt, fun, arg=None, kwarg=None, expr_form='glob',
              timeout=None, ret=None):
        '''
        Run a single command using the ``local`` client

        Wraps :meth:`low`.
        '''
        low = {
            'client': 'local',
            'tgt': tgt,
            'fun': fun,
        }

        if arg:
            low['arg'] = arg

        if kwarg:
            low['kwarg'] = kwarg

        if expr_form:
            low['expr_form'] = expr_form

        if timeout:
            low['timeout'] = timeout

        if ret:
            low['ret'] = ret

        return self.low([low], path='/')

    def local_async(self, tgt, fun, arg=None, kwarg=None, expr_form='glob',
                    timeout=None, ret=None):
        '''
        Run a single command using the ``local_async`` client

        Wraps :meth:`low`.
        '''
        low = {
            'client': 'local_async',
            'tgt': tgt,
            'fun': fun,
        }

        if arg:
            low['arg'] = arg

        if kwarg:
            low['kwarg'] = kwarg

        if expr_form:
            low['expr_form'] = expr_form

        if timeout:
            low['timeout'] = timeout

        if ret:
            low['ret'] = ret

        return self.low([low], path='/')

    def lookup_jid(self, jid):
        '''
        Get job results

        Wraps :meth:`runner`.
        '''

        return self.runner('jobs.lookup_jid', jid='{0}'.format(jid))

    def runner(self, fun, **kwargs):
        '''
        Run a single command using the ``runner`` client

        Usage::
          runner('jobs.lookup_jid', jid=12345)
        '''
        low = {
            'client': 'runner',
            'fun': fun,
        }

        low.update(kwargs)

        return self.low([low], path='/')

    def login(self, username, password, eauth):
        '''
        Authenticate with salt-api and return the user permissions and
        authentication token or an empty dict

        '''
        self.auth = self.req('/login', {
            'username': username,
            'password': password,
            'eauth': eauth}).get('return', [{}])[0]

        return self.auth

    def _construct_url(self, path):
        '''
        Construct the url to salt-api for the given path

        Args:
            path: the path to the salt-api resource

        >>> api = Pepper('https://localhost:8000/salt-api/')
        >>> api._construct_url('/login')
        'https://localhost:8000/salt-api/login'
        '''

        relative_path = path.lstrip('/')
        return urlparse.urljoin(self.api_url, relative_path)
