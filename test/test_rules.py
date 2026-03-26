"""Tests for the validation rules module."""

import pytest

from pvValidatorUtils.parser import parse_pv
from pvValidatorUtils.rules import (
    Severity,
    check_all_rules,
    check_device_index,
    check_element_characters,
    check_element_lengths,
    check_legacy_index,
    check_legacy_prefix,
    check_mtca_naming,
    check_pascal_case,
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
        assert has_error(check_property_length(c), "exceeds 25")

    def test_21_chars_warning(self):
        """ESS-0000757 §6.2: SHOULD max 20 chars. 21 chars = warning."""
        prop = "A" * 21
        c = parse(f"DTL-010:EMR-TT-001:{prop}")
        msgs = check_property_length(c)
        assert has_warning(msgs, "recommended 20")
        assert no_errors(msgs)  # Not an error, just a warning

    def test_20_chars_no_warning(self):
        prop = "A" * 20
        c = parse(f"DTL-010:EMR-TT-001:{prop}")
        msgs = check_property_length(c)
        assert not has_warning(msgs, "recommended")

    def test_suffix_sp_excluded(self):
        prop = "A" * 23 + "-SP"
        assert effective_property_length(prop) == 23

    def test_suffix_rb_excluded(self):
        prop = "A" * 23 + "-RB"
        assert effective_property_length(prop) == 23

    def test_short_property_warning(self):
        c = parse("DTL-010:EMR-TT-001:Te")
        msgs = check_property_length(c)
        assert has_warning(msgs, "below 4")

    @pytest.mark.parametrize("prop", ["On", "Off", "In", "Out", "Ok"])
    def test_known_short_properties_no_warning(self, prop):
        """ESS-0000757 Table 9: Known short state properties are valid."""
        c = parse(f"DTL-010:EMR-TT-001:{prop}")
        msgs = check_property_length(c)
        assert not has_warning(
            msgs, "below 4"
        ), f"Known property '{prop}' should not get a warning"

    def test_4char_no_warning(self):
        c = parse("DTL-010:EMR-TT-001:Temp")
        msgs = check_property_length(c)
        assert not has_warning(msgs, "below 4")


# ---------------------------------------------------------------------------
# Property Suffix
# ---------------------------------------------------------------------------


class TestPropertySuffix:

    @pytest.mark.parametrize(
        "suffix,fragment",
        [
            ("-S", "should end with -SP"),
            ("_S", "should end with -SP"),
            ("-RBV", "should end with -RB"),
            ("_RBV", "should end with -RB"),
            ("-R", "should not contain"),
            ("_R", "should not contain"),
        ],
    )
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

    @pytest.mark.parametrize(
        "pv,element_name",
        [
            ("ABCDEFG-010:EMR-TT-001:Temperature", "System"),
            ("DTL-ABCDEFG:EMR-TT-001:Temperature", "Subsystem"),
            ("DTL-010:ABCDEFG-TT-001:Temperature", "Discipline"),
            ("DTL-010:EMR-ABCDEFG-001:Temperature", "Device"),
        ],
    )
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
        msgs = check_property_uniqueness(
            "DTL-010:EMR-TT-001", ["Temperature", "Pressure", "Voltage"]
        )
        for pv_msgs in msgs.values():
            assert no_errors(pv_msgs)

    def test_exact_duplicate(self):
        msgs = check_property_uniqueness(
            "DTL-010:EMR-TT-001", ["Temperature", "Temperature"]
        )
        all_msgs = [m for pv_msgs in msgs.values() for m in pv_msgs]
        assert has_error(all_msgs, "duplication")

    def test_case_confusion(self):
        msgs = check_property_uniqueness(
            "DTL-010:EMR-TT-001", ["Temperature", "temperature"]
        )
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


# ---------------------------------------------------------------------------
# Legacy 5-Digit Index (ESS-0000757 Annex C)
# ---------------------------------------------------------------------------


class TestLegacy5DigitIndex:

    def test_5digit_cryo_warning(self):
        c = parse("CWM-CWS03:Cryo-PT-12345:Temperature")
        msgs = check_legacy_index(c)
        assert has_warning(msgs, "legacy")

    def test_4digit_cryo_ok(self):
        c = parse("CWM-CWS03:Cryo-PT-1234:Temperature")
        msgs = check_legacy_index(c)
        assert len(msgs) == 0

    def test_5digit_vac_warning(self):
        c = parse("ISrc:Vac-VG-12345:Pressure")
        msgs = check_legacy_index(c)
        assert has_warning(msgs, "legacy")

    def test_5digit_non_cryo_ok(self):
        """Non-Cryo/Vac disciplines don't trigger legacy warning."""
        c = parse("DTL-010:EMR-TT-12345:Temperature")
        msgs = check_legacy_index(c)
        assert len(msgs) == 0

    def test_high_level_no_check(self):
        c = parse("DTL-010::Temperature")
        msgs = check_legacy_index(c)
        assert len(msgs) == 0


# ---------------------------------------------------------------------------
# Pascal Case (ESS-0000757 §6.2 Rule 5)
# ---------------------------------------------------------------------------


class TestPascalCase:

    def test_all_uppercase_warning(self):
        c = parse("DTL-010:EMR-TT-001:TEMPERATURE")
        msgs = check_pascal_case(c)
        assert has_warning(msgs, "PascalCase")

    def test_all_lowercase_warning(self):
        c = parse("DTL-010:EMR-TT-001:temperature")
        msgs = check_pascal_case(c)
        assert has_warning(msgs, "PascalCase")

    def test_pascal_case_ok(self):
        c = parse("DTL-010:EMR-TT-001:Temperature")
        msgs = check_pascal_case(c)
        assert len(msgs) == 0

    def test_mixed_case_ok(self):
        c = parse("DTL-010:EMR-TT-001:TempMax")
        msgs = check_pascal_case(c)
        assert len(msgs) == 0

    @pytest.mark.parametrize("prop", ["On", "Off", "In", "Out", "Ok"])
    def test_short_exempt(self, prop):
        c = parse(f"DTL-010:EMR-TT-001:{prop}")
        msgs = check_pascal_case(c)
        assert len(msgs) == 0

    def test_internal_exempt(self):
        c = parse("DTL-010:EMR-TT-001:#DEBUGVALUE")
        msgs = check_pascal_case(c)
        assert len(msgs) == 0

    def test_with_suffix_sp(self):
        """Check applies to base property, not suffix."""
        c = parse("DTL-010:EMR-TT-001:TEMPERATURE-SP")
        msgs = check_pascal_case(c)
        assert has_warning(msgs, "PascalCase")

    def test_4char_exempt(self):
        """Properties <= 4 chars are exempt (could be abbreviations)."""
        c = parse("DTL-010:EMR-TT-001:TEMP")
        msgs = check_pascal_case(c)
        assert len(msgs) == 0


# ---------------------------------------------------------------------------
# MTCA Controller Naming (ESS-0000757 Annex A)
# ---------------------------------------------------------------------------


class TestMTCANaming:

    def test_ctrl_mtca_3digit_ok(self):
        c = parse("PBI-BCM01:Ctrl-MTCA-100:Status")
        msgs = check_mtca_naming(c)
        assert len(msgs) == 0

    def test_ctrl_mtca_wrong_index(self):
        c = parse("PBI-BCM01:Ctrl-MTCA-12:Status")
        msgs = check_mtca_naming(c)
        assert has_warning(msgs, "3 digits")

    def test_ctrl_cpu_3digit_ok(self):
        c = parse("PBI-BCM01:Ctrl-CPU-001:Status")
        msgs = check_mtca_naming(c)
        assert len(msgs) == 0

    def test_ctrl_evr_wrong_index(self):
        c = parse("PBI-BCM01:Ctrl-EVR-1234:Status")
        msgs = check_mtca_naming(c)
        assert has_warning(msgs, "3 digits")

    def test_non_ctrl_no_check(self):
        c = parse("DTL-010:EMR-TT-001:Temperature")
        msgs = check_mtca_naming(c)
        assert len(msgs) == 0


# ---------------------------------------------------------------------------
# Target Station Exception (ESS-0000757 Annex B)
# ---------------------------------------------------------------------------


class TestTargetException:

    def test_tgt_long_subsystem_info(self):
        """Target Station subsystems > 6 chars get INFO, not ERROR."""
        c = parse("Tgt-HeC1010:Proc-TT-003:Temperature")
        msgs = check_element_lengths(c)
        info = [
            m for m in msgs if m.severity == Severity.INFO and m.rule_id == "EXC-TGT"
        ]
        assert len(info) == 1

    def test_tgt_normal_subsystem_ok(self):
        c = parse("Tgt-HeC1:Proc-TT-003:Temperature")
        msgs = check_element_lengths(c)
        assert no_errors(msgs)

    def test_non_tgt_long_subsystem_error(self):
        """Non-Target systems still get ELEM-6 error."""
        c = parse("DTL-ABCDEFG:EMR-TT-001:Temperature")
        msgs = check_element_lengths(c)
        assert any(m.rule_id == "ELEM-6" for m in msgs)
