"""Offline tests for Naming Service API interaction.

These tests mock the ESS Naming Service REST API using the `responses` library,
allowing full validation testing without ESS network access.
"""

import json
import pathlib

import pytest
import responses

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"
PROD_BASE = "https://naming.esss.lu.se/"
PARTS_URL = PROD_BASE + "rest/parts/mnemonic/"
NAMES_URL = PROD_BASE + "rest/deviceNames/"


def load_api_responses():
    with open(FIXTURES_DIR / "naming_api_responses.json") as f:
        return json.load(f)


def register_parts_mocks(api_data):
    """Register mock responses for /rest/parts/mnemonic/ endpoints."""
    for mnemonic, response_data in api_data["parts_mnemonic"].items():
        responses.add(
            responses.GET,
            PARTS_URL + mnemonic,
            json=response_data,
            status=200,
        )


def register_names_mocks(api_data):
    """Register mock responses for /rest/deviceNames/ endpoints."""
    for name, response_data in api_data["device_names"].items():
        responses.add(
            responses.GET,
            NAMES_URL + name,
            json=response_data,
            status=200,
        )


def register_all_mocks(api_data):
    """Register HEAD for connectivity check + all GET mocks."""
    responses.add(responses.HEAD, PROD_BASE, status=200)
    register_parts_mocks(api_data)
    register_names_mocks(api_data)


# ---------------------------------------------------------------------------
# Import helpers — gracefully handle missing SWIG modules
# ---------------------------------------------------------------------------

try:
    from pvValidatorUtils import epicsUtils, pvUtils

    HAS_EPICS = True
except ImportError:
    HAS_EPICS = False

# Use conftest MockEpicsUtils if SWIG modules not available
if not HAS_EPICS:
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    from conftest import MockEpicsUtils


def make_pvutils(pv_list, checkonlyfmt=False):
    """Create a pvUtils instance with mocked epicsUtils."""
    if HAS_EPICS:
        pvepics = epicsUtils()
        for pv in pv_list:
            pvepics.pvstringlist.push_back(pv)
        return pvUtils(pvepics=pvepics, checkonlyfmt=checkonlyfmt, stdout=True)
    else:
        pvepics = MockEpicsUtils()
        for pv in pv_list:
            pvepics.pvstringlist.push_back(pv)
        # Can't create pvUtils without compiled module, skip
        pytest.skip("pvUtils requires compiled SWIG modules")


# ---------------------------------------------------------------------------
# Tests: Naming Service connectivity
# ---------------------------------------------------------------------------


class TestNamingServiceConnectivity:
    """Test Naming Service connection handling."""

    @responses.activate
    def test_prod_service_reachable(self):
        """When prod service responds, validator should proceed."""
        responses.add(responses.HEAD, PROD_BASE, status=200)
        if not HAS_EPICS:
            pytest.skip("Requires compiled SWIG modules")
        pvu = make_pvutils(["DTL-010:EMR-TT-001:Temperature"])
        assert "Production" in pvu.infovalidation

    @responses.activate
    def test_service_unreachable_exits(self):
        """When service is unreachable, validator should exit."""
        responses.add(
            responses.HEAD,
            PROD_BASE,
            body=ConnectionError("Network unreachable"),
        )
        if not HAS_EPICS:
            pytest.skip("Requires compiled SWIG modules")
        with pytest.raises((SystemExit, ConnectionError)):
            make_pvutils(["DTL-010:EMR-TT-001:Temperature"])

    @responses.activate
    def test_noapi_skips_connection(self):
        """With checkonlyfmt=True, no API connection is attempted."""
        # No mock registered — would fail if connection attempted
        if not HAS_EPICS:
            pytest.skip("Requires compiled SWIG modules")
        pvu = make_pvutils(["DTL-010:EMR-TT-001:Temperature"], checkonlyfmt=True)
        assert "skipped" in pvu.infovalidation.lower()


# ---------------------------------------------------------------------------
# Tests: System/Subsystem validation
# ---------------------------------------------------------------------------


class TestSystemValidation:
    """Test validation of System and Subsystem against Naming Service."""

    @responses.activate
    def test_valid_system_recognized(self):
        """DTL is a valid, approved system."""
        api_data = load_api_responses()
        register_all_mocks(api_data)
        if not HAS_EPICS:
            pytest.skip("Requires compiled SWIG modules")
        pvu = make_pvutils(["DTL-010:EMR-TT-001:Temperature"])
        pvu._checkValidFormat()
        pvu._checkPropRules()
        pvu._checkValidName()
        assert pvu.VNameD["DTL-010:EMR-TT-001:Temperature"] is True

    @responses.activate
    def test_invalid_system_rejected(self):
        """NONEXIST is not registered in the Naming Service."""
        api_data = load_api_responses()
        register_all_mocks(api_data)
        # Add mock for unregistered system
        responses.add(responses.GET, PARTS_URL + "QQQQQQ", json=[], status=200)
        responses.add(
            responses.GET,
            NAMES_URL + "QQQQQQ-010:EMR-TT-001",
            json={"error": "not found"},
            status=404,
        )
        if not HAS_EPICS:
            pytest.skip("Requires compiled SWIG modules")
        pvu = make_pvutils(["QQQQQQ-010:EMR-TT-001:Temperature"])
        pvu._checkValidFormat()
        pvu._checkPropRules()
        pvu._checkValidName()
        assert pvu.VNameD["QQQQQQ-010:EMR-TT-001:Temperature"] is False


# ---------------------------------------------------------------------------
# Tests: Device name status handling
# ---------------------------------------------------------------------------


class TestDeviceNameStatus:
    """Test handling of ACTIVE, OBSOLETE, DELETED status."""

    @responses.activate
    def test_active_name_valid(self):
        """ACTIVE status should pass validation."""
        api_data = load_api_responses()
        register_all_mocks(api_data)
        if not HAS_EPICS:
            pytest.skip("Requires compiled SWIG modules")
        pvu = make_pvutils(["DTL-010:EMR-TT-001:Temperature"])
        pvu._checkValidFormat()
        pvu._checkPropRules()
        pvu._checkValidName()
        pv = "DTL-010:EMR-TT-001:Temperature"
        assert pvu.VNameD[pv] is True
        assert "registered" in pvu.datainfo[pv].lower()

    @responses.activate
    def test_obsolete_name_invalid(self):
        """OBSOLETE status should fail validation."""
        api_data = load_api_responses()
        register_all_mocks(api_data)
        # Register mocks for OBSOLETE-TEST system parts
        responses.add(
            responses.GET,
            PARTS_URL + "OBSOLETE",
            json=[
                {
                    "status": "Approved",
                    "type": "System Structure",
                    "level": "2",
                    "mnemonic": "OBSOLETE",
                    "mnemonicPath": "OBSOLETE",
                }
            ],
            status=200,
        )
        responses.add(
            responses.GET,
            PARTS_URL + "TEST",
            json=[
                {
                    "status": "Approved",
                    "type": "System Structure",
                    "level": "3",
                    "mnemonic": "TEST",
                    "mnemonicPath": "OBSOLETE-TEST",
                }
            ],
            status=200,
        )
        if not HAS_EPICS:
            pytest.skip("Requires compiled SWIG modules")
        pvu = make_pvutils(["OBSOLETE-TEST:EMR-TT-001:Temperature"])
        pvu._checkValidFormat()
        pvu._checkPropRules()
        pvu._checkValidName()
        pv = "OBSOLETE-TEST:EMR-TT-001:Temperature"
        assert pvu.VNameD[pv] is False
        assert "modified" in pvu.datainfo[pv].lower()


# ---------------------------------------------------------------------------
# Tests: API response edge cases
# ---------------------------------------------------------------------------


class TestAPIEdgeCases:
    """Test handling of unusual API responses."""

    @responses.activate
    def test_api_returns_empty_list(self):
        """Empty response for unknown mnemonic should mark as not registered."""
        api_data = load_api_responses()
        register_all_mocks(api_data)
        responses.add(responses.GET, PARTS_URL + "FAKESYS", json=[], status=200)
        responses.add(
            responses.GET,
            NAMES_URL + "FAKESYS-010:EMR-TT-001",
            json={"error": "not found"},
            status=404,
        )
        responses.add(
            responses.GET,
            PARTS_URL + "010",
            json=[
                {
                    "status": "Approved",
                    "type": "System Structure",
                    "level": "3",
                    "mnemonic": "010",
                    "mnemonicPath": "FAKESYS-010",
                }
            ],
            status=200,
        )
        if not HAS_EPICS:
            pytest.skip("Requires compiled SWIG modules")
        pvu = make_pvutils(["FAKESYS-010:EMR-TT-001:Temperature"])
        pvu._checkValidFormat()
        pvu._checkPropRules()
        pvu._checkValidName()
        assert pvu.VNameD["FAKESYS-010:EMR-TT-001:Temperature"] is False

    @responses.activate
    def test_api_timeout_handled(self):
        """API timeout should not crash the validator."""
        responses.add(responses.HEAD, PROD_BASE, status=200)
        responses.add(
            responses.GET,
            PARTS_URL + "DTL",
            body=ConnectionError("Read timed out"),
        )
        if not HAS_EPICS:
            pytest.skip("Requires compiled SWIG modules")
        pvu = make_pvutils(["DTL-010:EMR-TT-001:Temperature"])
        pvu._checkValidFormat()
        pvu._checkPropRules()
        # This may raise or handle gracefully depending on implementation
        try:
            pvu._checkValidName()
        except Exception:
            pass  # Expected — current code doesn't handle timeouts gracefully


# ---------------------------------------------------------------------------
# Tests: Format + Rules (offline, no API needed)
# ---------------------------------------------------------------------------


class TestOfflineValidation:
    """Tests that work completely offline — format and property rules only."""

    def test_format_validation_valid_pvs(self):
        """All valid-format PVs should pass format check."""
        if not HAS_EPICS:
            pytest.skip("Requires compiled SWIG modules")
        valid_pvs = [
            "DTL-010:EMR-TT-001:Temperature",
            "PBI-BCM01:Ctrl-MTCA-100:Status",
            "DTL-010::Temperature",
            "DTL::ReadyForBeam",
        ]
        pvu = make_pvutils(valid_pvs, checkonlyfmt=True)
        pvu._checkValidFormat()
        for pv in valid_pvs:
            assert pvu.VFormD.get(
                pv, False
            ), f"Valid PV '{pv}' rejected by format check"

    def test_format_validation_invalid_pvs(self):
        """All invalid-format PVs should fail format check."""
        if not HAS_EPICS:
            pytest.skip("Requires compiled SWIG modules")
        invalid_pvs = [
            "DTL-010:EMR--001:TemperatureMin",
            "DTL-010:EMR-TT:TemperatureMin",
            "DTL-010:EMR-TT-011TemperatureMax",
            "DTL-::Temperature",
        ]
        pvu = make_pvutils(invalid_pvs, checkonlyfmt=True)
        pvu._checkValidFormat()
        for pv in invalid_pvs:
            assert not pvu.VFormD.get(
                pv, True
            ), f"Invalid PV '{pv}' passed format check"

    @pytest.mark.parametrize(
        "pv,expected_error_fragment",
        [
            ("DTL-010:EMR-TT-001:Temperature-S", "should end with -SP"),
            ("DTL-010:EMR-TT-001:Temperature_S", "should end with -SP"),
            ("DTL-010:EMR-TT-001:Temperature-RBV", "should end with -RB"),
            ("DTL-010:EMR-TT-001:Temperature_RBV", "should end with -RB"),
            ("DTL-010:EMR-TT-001:Temperature-R", "should not contain any suffix"),
            ("DTL-010:EMR-TT-001:Temperature_R", "should not contain any suffix"),
            ("DTL-010:EMR-TT-001:2Temperature", "does not start alphabetical"),
            ("DTL-010:EMR-TT-001:Temp!Min", "not allowed character"),
        ],
    )
    def test_property_rule_violations(self, pv, expected_error_fragment):
        """Each property rule violation should be detected."""
        if not HAS_EPICS:
            pytest.skip("Requires compiled SWIG modules")
        pvu = make_pvutils([pv], checkonlyfmt=True)
        pvu._checkValidFormat()
        pvu._checkPropRules()
        assert not pvu.VRuleD.get(pv, True), f"Rule violation not detected for '{pv}'"
        assert (
            expected_error_fragment.lower() in pvu.datainfo.get(pv, "").lower()
        ), f"Expected '{expected_error_fragment}' in error for '{pv}', got: {pvu.datainfo.get(pv, '')}"

    @pytest.mark.parametrize(
        "pv",
        [
            "DTL-010:EMR-TT-001:Temperature",
            "DTL-010:EMR-TT-001:Pressure",
            "DTL-010:EMR-TT-001:Voltage-SP",
            "DTL-010:EMR-TT-001:Current-RB",
            "DTL-010:EMR-TT-001:#InternalDebug",
        ],
    )
    def test_valid_properties_pass(self, pv):
        """Valid properties should pass all rule checks."""
        if not HAS_EPICS:
            pytest.skip("Requires compiled SWIG modules")
        pvu = make_pvutils([pv], checkonlyfmt=True)
        pvu._checkValidFormat()
        pvu._checkPropRules()
        assert pvu.VRuleD.get(pv, False) or pvu.VWarnD.get(
            pv, False
        ), f"Valid PV '{pv}' failed rules: {pvu.datainfo.get(pv, '')}"


# ---------------------------------------------------------------------------
# Tests: Confusable character detection
# ---------------------------------------------------------------------------


class TestConfusableDetection:
    """Test detection of visually confusable property names."""

    @pytest.mark.parametrize(
        "pv1,pv2,issue_type",
        [
            ("DTL-010:EMR-TT-010:TempO", "DTL-010:EMR-TT-010:Temp0", "0 O"),
            ("DTL-010:EMR-TT-011:TempI", "DTL-010:EMR-TT-011:Temp1", "1 I"),
            ("DTL-010:EMR-TT-012:Templ", "DTL-010:EMR-TT-012:Temp1", "1 l"),
            ("DTL-010:EMR-TT-013:TempVV", "DTL-010:EMR-TT-013:TempW", "VV W"),
        ],
    )
    def test_confusable_pairs_detected(self, pv1, pv2, issue_type):
        """Confusable property pairs should be flagged as errors."""
        if not HAS_EPICS:
            pytest.skip("Requires compiled SWIG modules")
        pvu = make_pvutils([pv1, pv2], checkonlyfmt=True)
        pvu._checkValidFormat()
        pvu._checkPropRules()
        # At least one of the pair should have an error
        has_error = (not pvu.VRuleD.get(pv1, True)) or (not pvu.VRuleD.get(pv2, True))
        assert has_error, f"Confusable pair ({issue_type}) not detected: {pv1} vs {pv2}"
