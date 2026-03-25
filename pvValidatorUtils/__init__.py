import sys

try:
    from .epicsUtils import epicsUtils  # noqa
except ImportError:
    epicsUtils = None  # SWIG module not compiled

from .pvUtils import pvUtils  # noqa

if sys.version_info >= (3, 8, 0):
    from importlib.metadata import distribution

    dist = distribution("pvValidatorUtils")
else:
    from pkg_resources import get_distribution

    dist = get_distribution("pvValidatorUtils")


version = dist.version
