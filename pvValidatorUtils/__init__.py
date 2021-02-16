import pkg_resources

from .epicsUtils import epicsUtils  # noqa
from .pvUtils import pvUtils  # noqa

version = pkg_resources.require("pvValidatorUtils")[0].version
