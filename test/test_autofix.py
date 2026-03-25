"""Tests for auto-fix suggestions."""

import pytest

from pvValidatorUtils.autofix import apply_fixes, suggest_fixes


class TestSuffixFixes:

    @pytest.mark.parametrize("pv,expected", [
        # -RBV/-RB and -R are auto-fixable (deterministic)
        ("DTL-010:EMR-TT-001:Temperature-RBV", "DTL-010:EMR-TT-001:Temperature-RB"),
        ("DTL-010:EMR-TT-001:Temperature_RBV", "DTL-010:EMR-TT-001:Temperature-RB"),
        ("DTL-010:EMR-TT-001:Temperature-R", "DTL-010:EMR-TT-001:Temperature"),
        ("DTL-010:EMR-TT-001:Temperature_R", "DTL-010:EMR-TT-001:Temperature"),
    ])
    def test_deterministic_suffix_fixes(self, pv, expected):
        result = apply_fixes(pv)
        assert result == expected, f"Expected {expected}, got {result}"

    def test_s_suffix_not_auto_fixable(self):
        """'-S' suffix needs human judgment — might not be a setpoint."""
        fixes = suggest_fixes("DTL-010:EMR-TT-001:Temperature-S")
        assert len(fixes) > 0
        assert not fixes[0].auto_fixable  # Needs human verification
        assert "-SP" in fixes[0].suggested  # But does suggest -SP

    def test_underscore_s_suffix_not_auto_fixable(self):
        """'_S' suffix needs human judgment too."""
        fixes = suggest_fixes("DTL-010:EMR-TT-001:Temperature_S")
        assert len(fixes) > 0
        assert not fixes[0].auto_fixable

    def test_valid_suffix_no_change(self):
        assert apply_fixes("DTL-010:EMR-TT-001:Temperature-SP") == "DTL-010:EMR-TT-001:Temperature-SP"
        assert apply_fixes("DTL-010:EMR-TT-001:Temperature-RB") == "DTL-010:EMR-TT-001:Temperature-RB"


class TestCaseFixes:

    def test_lowercase_to_uppercase(self):
        result = apply_fixes("DTL-010:EMR-TT-001:temperature")
        assert result == "DTL-010:EMR-TT-001:Temperature"

    def test_uppercase_no_change(self):
        assert apply_fixes("DTL-010:EMR-TT-001:Temperature") == "DTL-010:EMR-TT-001:Temperature"

    def test_internal_pv_no_case_fix(self):
        assert apply_fixes("DTL-010:EMR-TT-001:#debug") == "DTL-010:EMR-TT-001:#debug"


class TestNonFixable:

    def test_element_too_long_not_fixable(self):
        fixes = suggest_fixes("ABCDEFG-010:EMR-TT-001:Temperature")
        non_fixable = [f for f in fixes if not f.auto_fixable]
        assert len(non_fixable) > 0

    def test_invalid_format_not_fixable(self):
        fixes = suggest_fixes("TOTALLY::BROKEN::FORMAT")
        assert len(fixes) == 1
        assert not fixes[0].auto_fixable


class TestApplyFixes:

    def test_valid_pv_unchanged(self):
        pv = "DTL-010:EMR-TT-001:Temperature"
        assert apply_fixes(pv) == pv

    def test_multiple_fixes_chained(self):
        # lowercase + -RBV suffix (both auto-fixable)
        result = apply_fixes("DTL-010:EMR-TT-001:temperature-RBV")
        assert result == "DTL-010:EMR-TT-001:Temperature-RB"

    def test_s_suffix_not_applied_by_apply_fixes(self):
        # -S is NOT auto-fixable, so apply_fixes should NOT change it
        # (only suggest_fixes returns the suggestion)
        result = apply_fixes("DTL-010:EMR-TT-001:Temperature-S")
        assert result == "DTL-010:EMR-TT-001:Temperature-S"
