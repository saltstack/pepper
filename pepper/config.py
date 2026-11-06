"""
Read pepper's configuration file and environment variables
"""

import os
from configparser import ConfigParser

from pepper.exceptions import PepperException

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


def read(defaults=None, path=None, profile=None, environment=None, strict=False):
    """
    Read settings from a profile of the config file and from the environment

    Environment variables override the default profile. A profile named by
    the profile argument or PEPPERPROFILE keeps its own settings, and
    environment variables only fill in the ones it does not set, so an
    exported SALTAPI_URL cannot send that profile's credentials to another
    salt-api.

    :param defaults: a dict of setting names and their default values,
        :data:`DEFAULTS` if not given
    :param path: the config file, :func:`default_path` if not given
    :param profile: the profile, :func:`default_profile` if not given
    :param environment: True to let environment variables override any
        profile, False to ignore them, None (the default) for the rule above
    :param strict: raise an error if the config file was named, by path or
        PEPPERRC, and cannot be read, or the profile was named, by profile or
        PEPPERPROFILE, and is not in the file

    :raises PepperException: if strict is set and the named config file or
        profile cannot be found
    """
    path_named = path is not None or "PEPPERRC" in os.environ
    profile_named = profile is not None or "PEPPERPROFILE" in os.environ
    path = default_path() if path is None else path
    profile = default_profile() if profile is None else profile
    config = ConfigParser(interpolation=None)
    found = config.read(path)
    if strict:
        if path_named and not found:
            raise PepperException(f"Unable to read the pepper config file {path}")
        if profile_named and not config.has_section(profile):
            raise PepperException(f"Profile {profile} not found in {path}")

    results = dict(DEFAULTS if defaults is None else defaults)
    for key in results:
        in_profile = config.has_section(profile) and config.has_option(profile, key)
        if in_profile:
            results[key] = config.get(profile, key)
        if environment is False or key not in os.environ:
            continue
        if environment or not (profile_named and in_profile):
            results[key] = os.environ[key]
    return results
