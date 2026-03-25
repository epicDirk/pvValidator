"""Tests for the validation rules module."""

import pytest

from pvValidatorUtils.parser import parse_pv
from pvValidatorUtils.rules import (
    Severity,
    ValidationMessage,
    check_all_rules,
    check_device_index,
    check_element_characters,
    check_element_lengths,
    check_legacy_prefix,
    check_property_characters,
    check_property_length,
    check_property_suffix,
    check_property_uniqueness,
    check_pv_length,
    effective_property_length,
    normalize_for_confusion,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse(pv: str):
    """Parse a PV and assert it's valid."""
    c = parse_pv(pv)
    assert c is not None, f"Test setup error: '{pv}' should be parseable"
    return c


def has_error(msgs, fragment=""):
    """Check if any message is an ERROR containing fragment."""
    return any(
        m.severity == Severity.ERROR and fragment.lower() in m.message.lower()
        for m in msgs
    )


def has_warning(msgs, fragment=""):
    return any(
        m.severity == Severity.WARNING and fragment.lower() in m.message.lower()
        for m in msgs
    )


def has_info(msgs, fragment=""):
    return any(
        m.severity == Severity.INFO and fragment.lower() in m.message.lower()
        for m in msgs
    )


def no_errors(msgs):
    return not any(m.severity == Severity.ERROR for m in msgs)


# ---------------------------------------------------------------------------
# PV Length
# ---------------------------------------------------------------------------

class TestPVLength:
    def test_within_limit(self):
        c = parse("DTL-010:EMR-TT-001:Temperature")
        assert no_errors(check_pv_length(c))

    def test_at_limit_60(self):
        # Build a PV exactly 60 chars
        prop = "A" * (60 - len("DTL-010:EMR-TT-001:"))
        c = parse(f"DTL-010:EMR-TT-001:{prop}")
        assert no_errors(check_pv_length(c))

    def test_beyond_limit(self):
        prop = "A" * 50
        c = parse(f"DTL-010:EMR-TT-001:{prop}")
        assert has_error(check_pv_length(c), "beyond 60")


# ---------------------------------------------------------------------------
# Property Length
# ---------------------------------------------------------------------------

class TestPropertyLength:
    def test_normal_length(self):
        c = parse("DTL-010:EMR-TT-001:Temperature")
        assert no_errors(check_property_length(c))

    def test_at_limit_25(self):
        prop = "A" * 25
        c = parse(f"DTL-010:EMR-TT-001:{prop}")
        assert no_errors(check_property_length(c))

    def test_beyond_25(self):
        prop = "A" * 26
        c = parse(f"DTL-010:EMR-TT-001:{prop}")
        assert has_error(check_property_length(c), "beyond 25")

    def test_suffix_sp_excluded(self):
        # 23 chars + "-SP" = 26 total, but effective = 23
        prop = "A" * 23 + "-SP"
        assert effective_property_length(prop) == 23

    def test_suffix_rb_excluded(self):
        prop = "A" * 23 + "-RB"
        assert effective_property_length(prop) == 23

    def test_short_property_warning(self):
        c = parse("DTL-010:EMR-TT-001:Te")
        msgs = check_property_length(c)
        assert has_warning(msgs, "below 4")

    def test_4char_no_warning(self):
        c = parse("DTL-010:EMR-TT-001:Temp")
        msgs = check_property_length(c)
        assert not has_warning(msgs, "below 4")


# ---------------------------------------------------------------------------
# Property Suffix
# ---------------------------------------------------------------------------

class TestPropertySuffix:

    @pytest.mark.parametrize("suffix,fragment", [
        ("-S", "should end with -SP"),
        ("_S", "should end with -SP"),
        ("-RBV", "should end with -RB"),
        ("_RBV", "should end with -RB"),
        ("-R", "should not contain"),
        ("_R", "should not contain"),
    ])
    def test_invalid_suffixes(self, suffix, fragment):
        c = parse(f"DTL-010:EMR-TT-001:Temperature{suffix}")
        assert has_error(check_property_suffix(c), fragment)

    @pytest.mark.parametrize("suffix", ["-SP", "-RB"])
    def test_valid_suffixes(self, suffix):
        c = parse(f"DTL-010:EMR-TT-001:Temperature{suffix}")
        assert no_errors(check_property_suffix(c))


# ---------------------------------------------------------------------------
# Property Characters
# ---------------------------------------------------------------------------

class TestPropertyCharacters:
    def test_valid_property(self):
        c = parse("DTL-010:EMR-TT-001:Temperature")
        assert no_errors(check_property_characters(c))

    def test_starts_with_digit(self):
        c = parse("DTL-010:EMR-TT-001:2Temperature")
        assert has_error(check_property_characters(c), "not start alphabetical")

    def test_starts_lowercase_warning(self):
        c = parse("DTL-010:EMR-TT-001:temperature")
        assert has_warning(check_property_characters(c), "upper case")

    def test_disallowed_chars(self):
        c = parse("DTL-010:EMR-TT-001:Temp!Min")
        assert has_error(check_property_characters(c), "not allowed character")

    def test_internal_pv_hash(self):
        c = parse("DTL-010:EMR-TT-001:#InternalDebug")
        msgs = check_property_characters(c)
        assert has_info(msgs, "Internal PV")
        assert no_errors(msgs)

    def test_hash_wrong_position(self):
        c = parse("DTL-010:EMR-TT-001:Temp#Value")
        assert has_error(check_property_characters(c), "# character")


# ---------------------------------------------------------------------------
# Element Lengths
# ---------------------------------------------------------------------------

class TestElementLengths:
    def test_all_within_limit(self):
        c = parse("DTL-010:EMR-TT-001:Temperature")
        assert no_errors(check_element_lengths(c))

    def test_6char_at_boundary(self):
        c = parse("ABCDEF-010:EMR-TT-001:Temperature")
        assert no_errors(check_element_lengths(c))

    @pytest.mark.parametrize("pv,element_name", [
        ("ABCDEFG-010:EMR-TT-001:Temperature", "System"),
        ("DTL-ABCDEFG:EMR-TT-001:Temperature", "Subsystem"),
        ("DTL-010:ABCDEFG-TT-001:Temperature", "Discipline"),
        ("DTL-010:EMR-ABCDEFG-001:Temperature", "Device"),
    ])
    def test_7char_exceeds(self, pv, element_name):
        c = parse(pv)
        msgs = check_element_lengths(c)
        assert has_error(msgs, element_name)


# ---------------------------------------------------------------------------
# Element Characters
# ---------------------------------------------------------------------------

class TestElementCharacters:
    def test_valid_elements(self):
        c = parse("DTL-010:EMR-TT-001:Temperature")
        assert no_errors(check_element_characters(c))

    def test_system_starts_with_digit(self):
        c = parse("1DTL-010:EMR-TT-001:Temperature")
        assert has_error(check_element_characters(c), "must start with a letter")


# ---------------------------------------------------------------------------
# Device Index
# ---------------------------------------------------------------------------

class TestDeviceIndex:

    @pytest.mark.parametrize("idx", ["1", "01", "001", "100", "9999"])
    def test_scientific_valid(self, idx):
        c = parse(f"DTL-010:EMR-TT-{idx}:Temperature")
        assert no_errors(check_device_index(c))

    @pytest.mark.parametrize("idx", ["002", "002a", "002ab", "002abc"])
    def test_pid_valid(self, idx):
        c = parse(f"DTL-010:EMR-TT-{idx}:Temperature")
        assert no_errors(check_device_index(c))

    def test_index_too_long(self):
        c = parse("DTL-010:EMR-TT-1234567:Temperature")
        assert has_error(check_device_index(c), "exceeds 6")

    def test_high_level_no_index_check(self):
        c = parse("DTL-010::Temperature")
        assert no_errors(check_device_index(c))


# ---------------------------------------------------------------------------
# Legacy Prefix
# ---------------------------------------------------------------------------

class TestLegacyPrefix:

    @pytest.mark.parametrize("prefix", ["Cmd_", "P_", "FB_", "SP_"])
    def test_legacy_prefix_warning(self, prefix):
        c = parse(f"DTL-010:EMR-TT-001:{prefix}Value")
        assert has_warning(check_legacy_prefix(c), "legacy prefix")

    def test_no_legacy(self):
        c = parse("DTL-010:EMR-TT-001:Temperature")
        assert not has_warning(check_legacy_prefix(c))


# ---------------------------------------------------------------------------
# Confusable Normalization
# ---------------------------------------------------------------------------

class TestNormalization:
    def test_case_insensitive(self):
        assert normalize_for_confusion("Temp") == normalize_for_confusion("temp")

    def test_o_zero(self):
        assert normalize_for_confusion("TempO") == normalize_for_confusion("Temp0")

    def test_i_l_1(self):
        n = normalize_for_confusion
        assert n("TempI") == n("Templ") == n("Temp1")

    def test_vv_w(self):
        assert normalize_for_confusion("TempVV") == normalize_for_confusion("TempW")


# ---------------------------------------------------------------------------
# Property Uniqueness (O(n) algorithm)
# ---------------------------------------------------------------------------

class TestPropertyUniqueness:
    def test_no_duplicates(self):
        msgs = check_property_uniqueness("DTL-010:EMR-TT-001", ["Temperature", "Pressure", "Voltage"])
        for pv_msgs in msgs.values():
            assert no_errors(pv_msgs)

    def test_exact_duplicate(self):
        msgs = check_property_uniqueness("DTL-010:EMR-TT-001", ["Temperature", "Temperature"])
        all_msgs = [m for pv_msgs in msgs.values() for m in pv_msgs]
        assert has_error(all_msgs, "duplication")

    def test_case_confusion(self):
        msgs = check_property_uniqueness("DTL-010:EMR-TT-001", ["Temperature", "temperature"])
        all_msgs = [m for pv_msgs in msgs.values() for m in pv_msgs]
        assert has_error(all_msgs, "not unique")

    def test_o_zero_confusion(self):
        msgs = check_property_uniqueness("DTL-010:EMR-TT-001", ["TempO", "Temp0"])
        all_msgs = [m for pv_msgs in msgs.values() for m in pv_msgs]
        assert has_error(all_msgs, "not unique")

    def test_vv_w_confusion(self):
        msgs = check_property_uniqueness("DTL-010:EMR-TT-001", ["TempVV", "TempW"])
        all_msgs = [m for pv_msgs in msgs.values() for m in pv_msgs]
        assert has_error(all_msgs, "not unique")


# ---------------------------------------------------------------------------
# check_all_rules integration
# ---------------------------------------------------------------------------

class TestCheckAllRules:
    def test_valid_pv_no_errors(self):
        c = parse("DTL-010:EMR-TT-001:Temperature")
        msgs = check_all_rules(c)
        assert no_errors(msgs)

    def test_multiple_issues_detected(self):
        # Too long property + starts with digit
        c = parse("DTL-010:EMR-TT-001:2TemperatureTemperatureTemperatureTemp")
        msgs = check_all_rules(c)
        errors = [m for m in msgs if m.severity == Severity.ERROR]
        assert len(errors) >= 2
