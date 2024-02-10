'''
Pepper is a CLI front-end to salt-api
'''
from importlib.metadata import PackageNotFoundError, version

from pepper.libpepper import Pepper, PepperException

__all__ = ('__version__', 'Pepper', 'PepperException')

try:
    __version__ = version('salt_pepper')
except PackageNotFoundError:
    # package is not installed
    __version__ = None

# For backwards compatibility
version = __version__
sha = None
