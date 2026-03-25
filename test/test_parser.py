"""Tests for the PV name parser module."""

import pytest

from pvValidatorUtils.parser import (
    FMT_FULL,
    FMT_HIGH_LEVEL_SUBSYS,
    FMT_HIGH_LEVEL_SYS,
    FMT_NO_SUBSYSTEM,
    PVComponents,
    parse_pv,
    is_valid_format,
)


class TestParseValidFormats:
    """Test parsing of all 4 valid ESS PV formats."""

    @pytest.mark.parametrize("pv,sys,sub,dis,dev,idx,prop,fmt", [
        # Format 1: Sys-Sub:Dis-Dev-Idx:Property (full)
        ("DTL-010:EMR-TT-001:Temperature", "DTL", "010", "EMR", "TT", "001", "Temperature", FMT_FULL),
        ("PBI-BCM01:Ctrl-MTCA-100:Status", "PBI", "BCM01", "Ctrl", "MTCA", "100", "Status", FMT_FULL),
        ("CWM-CWS03:WtrC-PT-011:Pressure", "CWM", "CWS03", "WtrC", "PT", "011", "Pressure", FMT_FULL),
        ("Tgt-HeC1010:Proc-TT-003:Temperature", "Tgt", "HeC1010", "Proc", "TT", "003", "Temperature", FMT_FULL),
        ("ISrc-CS:ISS-Magtr-01:Current", "ISrc", "CS", "ISS", "Magtr", "01", "Current", FMT_FULL),
        # Format 2: Sys:Dis-Dev-Idx:Property (no subsystem)
        ("ISrc:ISS-Magtr-01:Current", "ISrc", "", "ISS", "Magtr", "01", "Current", FMT_NO_SUBSYSTEM),
        # Format 3: Sys-Sub::Property (high-level with subsystem)
        ("DTL-010::Temperature", "DTL", "010", "", "", "", "Temperature", FMT_HIGH_LEVEL_SUBSYS),
        ("CWM-CWS03::RunMode", "CWM", "CWS03", "", "", "", "RunMode", FMT_HIGH_LEVEL_SUBSYS),
        ("TD-M::OscillatorSyncStatus", "TD", "M", "", "", "", "OscillatorSyncStatus", FMT_HIGH_LEVEL_SUBSYS),
        # Format 4: Sys::Property (high-level system only)
        ("DTL::ReadyForBeam", "DTL", "", "", "", "", "ReadyForBeam", FMT_HIGH_LEVEL_SYS),
        ("Tgt::Status", "Tgt", "", "", "", "", "Status", FMT_HIGH_LEVEL_SYS),
        ("ISrc::Status", "ISrc", "", "", "", "", "Status", FMT_HIGH_LEVEL_SYS),
    ])
    def test_valid_formats(self, pv, sys, sub, dis, dev, idx, prop, fmt):
        result = parse_pv(pv)
        assert result is not None, f"Failed to parse valid PV: {pv}"
        assert result.system == sys
        assert result.subsystem == sub
        assert result.discipline == dis
        assert result.device == dev
        assert result.index == idx
        assert result.property == prop
        assert result.format_type == fmt
        assert result.raw == pv


class TestParseInvalidFormats:
    """Test that invalid PV formats return None."""

    @pytest.mark.parametrize("pv", [
        "",                                     # Empty string
        "DTL010EMRTT001Temperature",            # No colons
        "DTL-010:Temperature",                  # Only 1 colon (2 parts)
        "DTL-010:EMR-TT-001:Temp:Extra",        # Too many colons (4 parts)
        ":EMR-TT-001:Temperature",              # Empty system
        "DTL-:EMR-TT-001:Temperature",          # Empty subsystem after dash
        "DTL-010:EMR--001:Temperature",          # Empty device
        "DTL-010:EMR-TT:Temperature",           # Missing index (only 2 segments in device)
        "DTL-010:EMR-TT-001:",                  # Empty property
        "::::",                                  # All empty with extra colon
        "DTL-::Temperature",                    # Empty subsystem with device empty too (dash but nothing after)
    ])
    def test_invalid_formats(self, pv):
        result = parse_pv(pv)
        assert result is None, f"Should have rejected invalid PV: {pv}"


class TestParseEdgeCases:
    """Test boundary conditions."""

    def test_none_input(self):
        assert parse_pv(None) is None

    def test_int_input(self):
        assert parse_pv(123) is None

    def test_single_char_elements(self):
        result = parse_pv("A-B:C-D-1:E")
        assert result is not None
        assert result.system == "A"
        assert result.subsystem == "B"
        assert result.discipline == "C"
        assert result.device == "D"
        assert result.index == "1"
        assert result.property == "E"

    def test_internal_pv(self):
        result = parse_pv("DTL-010:EMR-TT-001:#InternalDebug")
        assert result is not None
        assert result.is_internal is True
        assert result.property == "#InternalDebug"

    def test_property_with_suffix(self):
        result = parse_pv("DTL-010:EMR-TT-001:Temperature-SP")
        assert result is not None
        assert result.property == "Temperature-SP"

    def test_property_with_dash(self):
        result = parse_pv("DTL-010:EMR-TT-001:Temp-Max")
        assert result is not None
        assert result.property == "Temp-Max"

    def test_property_with_underscore(self):
        result = parse_pv("DTL-010:EMR-TT-001:SKID_Ok")
        assert result is not None
        assert result.property == "SKID_Ok"


class TestPVComponents:
    """Test PVComponents dataclass methods."""

    def test_ess_name_full(self):
        c = parse_pv("DTL-010:EMR-TT-001:Temperature")
        assert c.ess_name == "DTL-010:EMR-TT-001"

    def test_ess_name_no_subsystem(self):
        c = parse_pv("ISrc:ISS-Magtr-01:Current")
        assert c.ess_name == "ISrc:ISS-Magtr-01"

    def test_ess_name_high_level_subsys(self):
        c = parse_pv("DTL-010::Temperature")
        assert c.ess_name == "DTL-010"

    def test_ess_name_high_level_sys(self):
        c = parse_pv("DTL::ReadyForBeam")
        assert c.ess_name == "DTL"

    def test_is_high_level(self):
        assert parse_pv("DTL::Status").is_high_level is True
        assert parse_pv("DTL-010::Temp").is_high_level is True
        assert parse_pv("DTL-010:EMR-TT-001:Temp").is_high_level is False

    def test_to_list(self):
        c = parse_pv("DTL-010:EMR-TT-001:Temperature")
        assert c.to_list() == ["DTL", "010", "EMR", "TT", "001", "Temperature"]

    def test_to_list_high_level(self):
        c = parse_pv("DTL::ReadyForBeam")
        assert c.to_list() == ["DTL", "", "", "", "", "ReadyForBeam"]


class TestIsValidFormat:
    """Test the convenience function."""

    def test_valid(self):
        assert is_valid_format("DTL-010:EMR-TT-001:Temperature") is True

    def test_invalid(self):
        assert is_valid_format("not-a-valid-pv") is False

    def test_empty(self):
        assert is_valid_format("") is False
