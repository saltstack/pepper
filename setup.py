#!/usr/bin/env python
'''
A CLI front-end to a running salt-api system

'''
import json
import os

from setuptools import setup
from distutils.command import sdist, install_data

setup_kwargs = {
    'name': 'salt-pepper',
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
    'entry_points': {
        'console_scripts': [
            'pepper = pepper.cli:pepper_cli'
        ]
    }
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

def write_version_file(base_dir):
    ver_path = os.path.join(base_dir, 'pepper', 'version.json')

    with open(ver_path, 'wb') as f:
        version = read_version_tag()
        json.dump({'version': version}, f)

class PepperSdist(sdist.sdist):
    '''
    Write the version.json file to the sdist tarball build directory
    '''
    def make_release_tree(self, base_dir, files):
        sdist.sdist.make_release_tree(self, base_dir, files)
        write_version_file(base_dir)

class PepperInstallData(install_data.install_data):
    '''
    Write the version.json file to the installation directory
    '''
    def run(self):
        install_cmd = self.get_finalized_command('install')
        install_dir = getattr(install_cmd, 'install_lib')
        write_version_file(install_dir)

        return install_data.install_data.run(self)

if __name__ == '__main__':
    setup(cmdclass={
        'sdist': PepperSdist,
        'install_data': PepperInstallData,
    }, version=read_version_tag(), **setup_kwargs)
