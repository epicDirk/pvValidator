from .epicsUtils import epicsUtils
from .pvUtils import pvUtils

import pkg_resources  
version =  pkg_resources.require("pvValidatorUtils")[0].version

