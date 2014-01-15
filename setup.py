#!/usr/bin/env python
'''
A CLI front-end to a running salt-api system

'''
import json
import os

from distutils.core import setup
from distutils.command.sdist import sdist

setup_kwargs = {
    'name': 'pepper',
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
    'package_data': {
        'pepper': ['version.json'],
    },
    'data_files': [
        ('share/man/man1', ['doc/man/pepper.1']),
    ],
    'scripts': [
        'scripts/pepper'
    ],
}

def read_version_tag():
    git_dir = os.path.join(os.path.dirname(__file__), '.git')

    if os.path.isdir(git_dir):
        import subprocess

        try:
            p = subprocess.Popen(['git', 'describe'],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = p.communicate()
        except Exception:
            pass
        else:
            return out.strip() or None

    return None

class PepperSdist(sdist):
    def make_release_tree(self, base_dir, files):
        sdist.make_release_tree(self, base_dir, files)

        ver_path = os.path.join(base_dir, 'pepper', 'version.json')

        with open(ver_path, 'wb') as f:
            version = read_version_tag()
            json.dump({'version': version}, f)

if __name__ == '__main__':
    setup(cmdclass={'sdist': PepperSdist}, version=read_version_tag(),
            **setup_kwargs)
