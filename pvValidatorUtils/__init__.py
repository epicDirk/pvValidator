try:
    from .epicsUtils import epicsUtils  # noqa
except ImportError:
    epicsUtils = None  # SWIG module not compiled

from importlib.metadata import distribution

from .pvUtils import pvUtils  # noqa

version = distribution("pvValidatorUtils").version
