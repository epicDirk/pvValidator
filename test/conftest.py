"""Shared fixtures and configuration for pvValidator tests.

Markers:
    ess_network: Test requires ESS Naming Service network access
    epics_ioc: Test requires a running EPICS IOC

Usage:
    pytest test/                        # Run offline tests only (default)
    pytest test/ --ess-network          # Include ESS network tests
    pytest test/ -m "not epics_ioc"     # Exclude IOC tests explicitly
"""

import json
import pathlib

import pytest

# ---------------------------------------------------------------------------
# CLI options
# ---------------------------------------------------------------------------


def pytest_addoption(parser):
    parser.addoption(
        "--ess-network",
        action="store_true",
        default=False,
        help="Run tests that require ESS Naming Service network access",
    )


# ---------------------------------------------------------------------------
# Markers
# ---------------------------------------------------------------------------


def pytest_configure(config):
    config.addinivalue_line("markers", "ess_network: requires ESS network access")
    config.addinivalue_line("markers", "epics_ioc: requires running EPICS IOC")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--ess-network"):
        skip_network = pytest.mark.skip(reason="needs --ess-network option to run")
        for item in items:
            if "ess_network" in item.keywords:
                item.add_marker(skip_network)

    # Always skip IOC tests unless explicitly included
    skip_ioc = pytest.mark.skip(
        reason="needs running EPICS IOC (mark with @pytest.mark.epics_ioc)"
    )
    for item in items:
        if "epics_ioc" in item.keywords:
            item.add_marker(skip_ioc)


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"
TEST_DIR = pathlib.Path(__file__).parent


def fixture_path(name: str) -> str:
    """Return absolute path to a test fixture file."""
    return str(FIXTURES_DIR / name)


def test_file_path(name: str) -> str:
    """Return absolute path to a file in the test/ directory."""
    return str(TEST_DIR / name)


# ---------------------------------------------------------------------------
# Mock epicsUtils (no EPICS dependency needed)
# ---------------------------------------------------------------------------


class MockEpicsUtils:
    """Lightweight mock for epicsUtils that doesn't need SWIG/EPICS.

    Provides the same interface as the C++ epicsUtils class:
    - pvstringlist: list of PV name strings
    - getAddress: server address string
    - getVersion: EPICS version string
    """

    def __init__(self):
        self.pvstringlist = PVStringList()
        self.getAddress = ""
        self.getVersion = "Mock EPICS (no compiled module)"


class PVStringList:
    """Mock for std::vector<std::string> exposed via SWIG."""

    def __init__(self):
        self._data = []

    def push_back(self, item):
        self._data.append(item)

    def size(self):
        return len(self._data)

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def __getitem__(self, idx):
        return self._data[idx]


@pytest.fixture
def mock_epics():
    """Provides a MockEpicsUtils object — no SWIG/EPICS compilation needed."""
    return MockEpicsUtils()


@pytest.fixture
def mock_epics_with_pvs():
    """Factory fixture: returns a function that creates MockEpicsUtils with given PV list."""

    def _factory(pv_list):
        m = MockEpicsUtils()
        for pv in pv_list:
            m.pvstringlist.push_back(pv)
        return m

    return _factory


# ---------------------------------------------------------------------------
# Naming Service API mock responses
# ---------------------------------------------------------------------------


@pytest.fixture
def naming_api_responses():
    """Load mock API responses from fixtures/naming_api_responses.json."""
    path = FIXTURES_DIR / "naming_api_responses.json"
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# VCR Cassettes (recorded from live ESS Naming Service)
# ---------------------------------------------------------------------------

CASSETTES_DIR = pathlib.Path(__file__).parent / "cassettes"


@pytest.fixture
def vcr_cassettes():
    """Load VCR cassettes if they exist (recorded by record_cassettes.py).

    Returns None if cassettes haven't been recorded yet.
    """
    cassette_file = CASSETTES_DIR / "naming_service_prod.json"
    if not cassette_file.exists():
        return None
    with open(cassette_file) as f:
        return json.load(f)


def has_cassettes() -> bool:
    """Check if VCR cassettes have been recorded."""
    return (CASSETTES_DIR / "naming_service_prod.json").exists()
