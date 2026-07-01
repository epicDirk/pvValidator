"""pvValidatorUtils — ESS EPICS PV name validator.

The package import is kept light on purpose: the pure-Python modules (parser,
rules, reporter, autofix, naming_client, rule_loader) must be importable without
the compiled SWIG extensions or the curses TUI. Therefore the heavy `pvUtils`
orchestrator is exposed lazily via module __getattr__ (PEP 562) and the SWIG
modules are guarded. This is what lets `import pvValidatorUtils.parser` and the
offline test suite run on plain Windows (no `_curses`) and in CI without EPICS.
"""

# SWIG extensions are optional — they are only needed for the EPICS input paths
# (-s IOC server, -e db file, -m substitution file). Guarded so a pure-Python
# import never fails; consumers must handle `epicsUtils is None` / `msiUtils is None`.
try:
    from .epicsUtils import epicsUtils  # noqa: F401
except ImportError:
    epicsUtils = None  # SWIG module not compiled

try:
    from . import (  # noqa: F401 — the SWIG *module*; pvUtils calls msiUtils.msiUtils(...)
        msiUtils,
    )
except ImportError:
    msiUtils = None  # SWIG module not compiled

# Package version from installed metadata. Falls back gracefully when imported
# from a bare source tree (no install), so pure-Python use never raises here.
try:
    from importlib.metadata import version as _pkg_version

    version = _pkg_version("pvValidatorUtils")
except Exception:  # pragma: no cover - metadata absent in an uninstalled tree
    version = "0.0.0+unknown"


def __getattr__(name):
    """Lazily expose the heavy `pvUtils` orchestrator class.

    `from pvValidatorUtils import pvUtils` must return the *class*, but importing
    the `pvUtils` submodule also auto-binds it as a package attribute (the module,
    not the class). We import it here on first access and pin the class onto the
    package so subsequent lookups stay consistent (class, not module).
    """
    if name == "pvUtils":
        import sys

        from .pvUtils import pvUtils as _pvUtils_cls

        setattr(sys.modules[__name__], "pvUtils", _pvUtils_cls)
        return _pvUtils_cls
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
