"""
Read pepper's configuration file and environment variables
"""

import os
from configparser import ConfigParser

#: Settings that can be given in a .pepperrc profile or the environment
DEFAULTS = {
    "SALTAPI_URL": "https://localhost:8000/",
    "SALTAPI_USER": None,
    "SALTAPI_PASS": None,
    "SALTAPI_EAUTH": "auto",
    "SALTAPI_CA_BUNDLE": None,
    "SALTAPI_CLIENT_CERT": None,
    "SALTAPI_CLIENT_CERT_KEY": None,
}


def default_path():
    """
    The config file named by PEPPERRC, or ~/.pepperrc
    """
    return os.environ.get(
        "PEPPERRC", os.path.join(os.path.expanduser("~"), ".pepperrc")
    )


def default_profile():
    """
    The profile named by PEPPERPROFILE, or main
    """
    return os.environ.get("PEPPERPROFILE", "main")


def read(defaults=None, path=None, profile=None, environment=True):
    """
    Read settings from a profile of the config file, then from the environment,
    which takes precedence

    :param defaults: a dict of setting names and their default values,
        :data:`DEFAULTS` if not given
    :param path: the config file, :func:`default_path` if not given
    :param profile: the profile, :func:`default_profile` if not given
    :param environment: let environment variables override the file
    """
    path = default_path() if path is None else path
    profile = default_profile() if profile is None else profile
    config = ConfigParser(interpolation=None)
    config.read(path)

    results = dict(DEFAULTS if defaults is None else defaults)
    for key in results:
        if config.has_section(profile) and config.has_option(profile, key):
            results[key] = config.get(profile, key)
        if environment:
            results[key] = os.environ.get(key, results[key])
    return results
