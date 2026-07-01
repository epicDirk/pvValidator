try:
    from .epicsUtils import epicsUtils  # noqa
except ImportError:
    epicsUtils = None  # SWIG module not compiled

try:
    from .msiUtils import msiUtils  # noqa
except ImportError:
    msiUtils = None  # SWIG module not compiled — needed only for the EPICS `-e` db path

from importlib.metadata import distribution

from .pvUtils import pvUtils  # noqa

version = distribution("pvValidatorUtils").version
