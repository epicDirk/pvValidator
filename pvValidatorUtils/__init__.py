from importlib.metadata import distribution

from .epicsUtils import epicsUtils  # noqa
from .pvUtils import pvUtils  # noqa

version = distribution("pvValidatorUtils").version
