#!/usr/bin/env python
'''
A CLI front-end to a running salt-api system

'''
import setuptools

with open("README.rst", "r") as fh:
    long_description = fh.read()

setup_kwargs = {
    'name': 'salt-pepper',
    'description': __doc__.strip(),
    'author': 'Seth House',
    'author_email': 'shouse@saltstack.com',
    'url': 'http://saltstack.com',
    'long_description': long_description,
    'long_description_content_type': "text/x-rst",
    'use_scm_version': True,
    'setup_requires': ['setuptools_scm'],
    'classifiers': [
        'Programming Language :: Python',
        'Programming Language :: Cython',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
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
    'extras_require': {
        'kerberos': ["requests-gssapi>=1.1.0"],
    },
    'scripts': [
        'scripts/pepper',
    ]
}


if __name__ == '__main__':
    setuptools.setup(**setup_kwargs)
