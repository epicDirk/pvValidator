"""Tests using real VCR cassettes from the ESS Naming Service.

These tests replay recorded API responses from naming.esss.lu.se.
No network access needed — the cassettes were recorded once and committed.
"""

import json
import pathlib
import re

import pytest
import responses

CASSETTES_DIR = pathlib.Path(__file__).parent / "cassettes"
CASSETTE_FILE = CASSETTES_DIR / "naming_service_prod.json"
PROD_BASE = "https://naming.esss.lu.se/"
PARTS_URL = PROD_BASE + "rest/parts/mnemonic/"
NAMES_URL = PROD_BASE + "rest/deviceNames/"

# Skip all tests if cassettes haven't been recorded yet
pytestmark = pytest.mark.skipif(
    not CASSETTE_FILE.exists(),
    reason="No cassettes recorded — run test/record_cassettes.sh on ESS network first",
)


@pytest.fixture(scope="module")
def cassettes():
    with open(CASSETTE_FILE) as f:
        return json.load(f)


@pytest.fixture(autouse=True)
def mock_naming_service(cassettes):
    """Register all cassette data + catch-all for unknown URLs."""
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        # HEAD for connectivity
        rsps.add(responses.HEAD, PROD_BASE, status=200)

        # Exact matches from cassettes (registered FIRST = higher priority)
        for mnemonic, data in cassettes.get("parts_mnemonic", {}).items():
            rsps.add(responses.GET, PARTS_URL + mnemonic, json=data, status=200)
        for name, data in cassettes.get("device_names", {}).items():
            rsps.add(responses.GET, NAMES_URL + name, json=data, status=200)

        # Catch-all for any parts/names URL not in cassettes
        rsps.add(
            responses.GET, re.compile(r".*/rest/parts/mnemonic/.*"), json=[], status=200
        )
        rsps.add(
            responses.GET,
            re.compile(r".*/rest/deviceNames/.*"),
            json={"status": "NOT_FOUND"},
            status=200,
        )

        yield rsps


# ---------------------------------------------------------------------------
# Import pvUtils (needs compiled SWIG modules)
# ---------------------------------------------------------------------------

try:
    from pvValidatorUtils import epicsUtils, pvUtils

    HAS_EPICS = True
except ImportError:
    HAS_EPICS = False

skipno = pytest.mark.skipif(not HAS_EPICS, reason="Requires compiled SWIG modules")


def make_pvutils(pv_list, checkonlyfmt=False):
    pvepics = epicsUtils()
    for pv in pv_list:
        pvepics.pvstringlist.push_back(pv)
    return pvUtils(pvepics=pvepics, checkonlyfmt=checkonlyfmt, stdout=True)


# ---------------------------------------------------------------------------
# Tests: Real ESS system validation (from cassettes)
# ---------------------------------------------------------------------------


class TestRealSystems:
    """Validate real ESS systems against cassette data."""

    @skipno
    @pytest.mark.parametrize(
        "system",
        ["DTL", "PBI", "ISrc", "Tgt", "CWM", "YMIR", "LOKI", "DREAM", "RFQ", "TD"],
    )
    def test_known_systems_valid(self, system):
        """Known ESS systems should be recognized."""
        pvu = make_pvutils([f"{system}-010:EMR-TT-001:Temperature"], checkonlyfmt=True)
        pvu._checkValidFormat()
        assert pvu.VFormD[f"{system}-010:EMR-TT-001:Temperature"] is True

    @skipno
    def test_dtl_010_registered(self):
        """DTL-010:EMR-TT-001 is a registered ACTIVE device name."""
        pvu = make_pvutils(["DTL-010:EMR-TT-001:Temperature"])
        pvu._checkValidFormat()
        pvu._checkPropRules()
        pvu._checkValidName()
        pv = "DTL-010:EMR-TT-001:Temperature"
        assert pvu.VNameD[pv] is True
        assert "registered" in pvu.datainfo[pv].lower()

    @skipno
    def test_pbi_bcm01_registered(self):
        """PBI-BCM01:Ctrl-MTCA-100 is a registered ACTIVE device name."""
        pvu = make_pvutils(["PBI-BCM01:Ctrl-MTCA-100:Status"])
        pvu._checkValidFormat()
        pvu._checkPropRules()
        pvu._checkValidName()
        pv = "PBI-BCM01:Ctrl-MTCA-100:Status"
        assert pvu.VNameD[pv] is True

    @skipno
    def test_nonexistent_system_rejected(self):
        """A fake system should fail name validation."""
        pvu = make_pvutils(["QQQQQQ-010:EMR-TT-001:Temperature"])
        pvu._checkValidFormat()
        pvu._checkPropRules()
        pvu._checkValidName()
        pv = "QQQQQQ-010:EMR-TT-001:Temperature"
        assert pvu.VNameD[pv] is False
        assert (
            "not active" in pvu.datainfo[pv].lower()
            or "not registered" in pvu.datainfo[pv].lower()
        )


class TestRealSubsystems:
    """Validate real ESS subsystems against cassette data."""

    @skipno
    def test_dtl_010_subsystem(self):
        """010 is a valid subsystem of DTL."""
        pvu = make_pvutils(["DTL-010:EMR-TT-001:Temperature"])
        pvu._checkValidFormat()
        pvu._checkPropRules()
        pvu._checkValidName()
        pv = "DTL-010:EMR-TT-001:Temperature"
        assert pvu.VNameD[pv] is True

    @skipno
    def test_pbi_bcm01_subsystem(self):
        """BCM01 is a valid subsystem of PBI."""
        pvu = make_pvutils(["PBI-BCM01:Ctrl-MTCA-100:Status"])
        pvu._checkValidFormat()
        pvu._checkPropRules()
        pvu._checkValidName()
        assert pvu.VNameD["PBI-BCM01:Ctrl-MTCA-100:Status"] is True


class TestRealDisciplines:
    """Validate real ESS disciplines against cassette data."""

    @skipno
    @pytest.mark.parametrize(
        "pv,should_pass",
        [
            ("DTL-010:EMR-TT-001:Temperature", True),  # EMR is real
            ("CWM-CWS03:WtrC-PT-011:Pressure", True),  # WtrC is real
            ("PBI-BCM01:Ctrl-MTCA-100:Status", True),  # Ctrl is real
        ],
    )
    def test_known_disciplines(self, pv, should_pass):
        pvu = make_pvutils([pv])
        pvu._checkValidFormat()
        pvu._checkPropRules()
        pvu._checkValidName()
        assert pvu.VNameD[pv] is should_pass


class TestRealDeviceNames:
    """Validate real registered device names."""

    @skipno
    def test_full_validation_pipeline(self):
        """Run the complete validation on known-good PVs from ESS-0000757 examples."""
        good_pvs = [
            "DTL-010:EMR-TT-001:Temperature",
        ]
        pvu = make_pvutils(good_pvs)
        pvu._checkValidFormat()
        pvu._checkPropRules()
        pvu._checkValidName()
        for pv in good_pvs:
            assert pvu.VFormD[pv] is True, f"Format check failed for {pv}"
            assert (
                pvu.VNameD[pv] is True
            ), f"Name check failed for {pv}: {pvu.datainfo.get(pv, '')}"


# ---------------------------------------------------------------------------
# Tests: Cassette data integrity
# ---------------------------------------------------------------------------


class TestCassetteData:
    """Verify the cassette file itself is well-formed."""

    def test_cassette_has_parts(self, cassettes):
        assert "parts_mnemonic" in cassettes
        assert len(cassettes["parts_mnemonic"]) > 20

    def test_cassette_has_device_names(self, cassettes):
        assert "device_names" in cassettes
        assert len(cassettes["device_names"]) > 5

    def test_dtl_system_in_cassettes(self, cassettes):
        dtl = cassettes["parts_mnemonic"].get("DTL", [])
        assert len(dtl) > 0
        approved = [x for x in dtl if x.get("status") == "Approved"]
        assert len(approved) > 0

    def test_device_name_has_status(self, cassettes):
        for name, data in cassettes["device_names"].items():
            if isinstance(data, dict) and "status" in data:
                assert data["status"] in (
                    "ACTIVE",
                    "OBSOLETE",
                    "DELETED",
                    "",
                ), f"Unexpected status '{data['status']}' for {name}"

    def test_metadata_present(self, cassettes):
        assert "_metadata" in cassettes
        assert "naming.esss.lu.se" in cassettes["_metadata"].get("source", "")
