#!/usr/bin/env python
'''
A CLI front-end to a running salt-api system

'''
import os
from distutils.core import setup

version_f = os.path.join(os.path.abspath(
    os.path.dirname(__file__)), 'pepper', 'version.py')

exec(compile(open(version_f).read(), version_f, 'exec'))

setup_kwargs = {
    'name': 'pepper',
    'version': __version__,
    'description': __doc__,
    'author': 'Seth House',
    'author_email': 'shouse@saltstack.com',
    'url': 'http://saltstack.com',
    'classifiers': [
        'Programming Language :: Python',
        'Programming Language :: Cython',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: POSIX :: Linux',
        'Topic :: System :: Clustering',
        'Topic :: System :: Distributed Computing',
    ],
    'packages': [
        'pepper',
    ],
    'data_files': [
        ('share/man/man1', ['doc/man/pepper.1']),
    ],
    'scripts': [
        'scripts/salt'
    ],
}

if __name__ == '__main__':
    setup(**setup_kwargs)
