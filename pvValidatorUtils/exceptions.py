"""Exception hierarchy for pvValidator.

Replaces sys.exit() calls with proper exceptions that callers can handle.
Only the CLI entry point (pvValidator.py) should call sys.exit().
"""


class PVValidatorError(Exception):
    """Base exception for all pvValidator errors."""

    pass


class NamingServiceError(PVValidatorError):
    """Cannot connect to or query the ESS Naming Service."""

    pass


class NamingServiceConnectionError(NamingServiceError):
    """Failed to establish connection to the Naming Service."""

    pass


class NamingServiceResponseError(NamingServiceError):
    """Unexpected response from the Naming Service."""

    pass


class InputError(PVValidatorError):
    """Invalid input file or configuration."""

    pass


class FileNotFoundError_(PVValidatorError):
    """Input file does not exist."""

    pass


class MacroSubstitutionError(PVValidatorError):
    """Unresolved macros in EPICS DB or substitution file."""

    pass


class EPICSConnectionError(PVValidatorError):
    """Cannot connect to EPICS IOC server."""

    pass
