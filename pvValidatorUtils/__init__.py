try:
    from .epicsUtils import epicsUtils  # noqa
except ImportError:
    epicsUtils = None  # SWIG module not compiled

from .pvUtils import pvUtils  # noqa

from importlib.metadata import distribution
version = distribution("pvValidatorUtils").version
