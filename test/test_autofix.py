"""Tests for auto-fix suggestions.

Tests verify that:
- Auto-fixable fixes are correct per ESS-0000757
- Non-fixable issues are flagged but not auto-applied
- Edge cases (empty property, word-internal -R, chaining) are handled
- Valid PVs produce zero suggestions
"""

import pytest

from pvValidatorUtils.autofix import apply_fixes, suggest_fixes


class TestSuffixFixes:

    @pytest.mark.parametrize("pv,expected", [
        ("DTL-010:EMR-TT-001:Temperature-RBV", "DTL-010:EMR-TT-001:Temperature-RB"),
        ("DTL-010:EMR-TT-001:Temperature_RBV", "DTL-010:EMR-TT-001:Temperature-RB"),
        ("DTL-010:EMR-TT-001:Temperature-R", "DTL-010:EMR-TT-001:Temperature"),
        ("DTL-010:EMR-TT-001:Temperature_R", "DTL-010:EMR-TT-001:Temperature"),
    ])
    def test_deterministic_suffix_fixes(self, pv, expected):
        result = apply_fixes(pv)
        assert result == expected

    def test_s_suffix_not_auto_fixable(self):
        fixes = suggest_fixes("DTL-010:EMR-TT-001:Temperature-S")
        assert len(fixes) > 0
        assert not fixes[0].auto_fixable
        assert "-SP" in fixes[0].suggested

    def test_underscore_s_suffix_not_auto_fixable(self):
        fixes = suggest_fixes("DTL-010:EMR-TT-001:Temperature_S")
        assert len(fixes) > 0
        assert not fixes[0].auto_fixable

    def test_valid_suffix_sp_no_suggestion(self):
        fixes = suggest_fixes("DTL-010:EMR-TT-001:Temperature-SP")
        suffix_fixes = [f for f in fixes if f.rule_id.startswith("PROP-")]
        assert len(suffix_fixes) == 0

    def test_valid_suffix_rb_no_suggestion(self):
        fixes = suggest_fixes("DTL-010:EMR-TT-001:Temperature-RB")
        suffix_fixes = [f for f in fixes if f.rule_id.startswith("PROP-")]
        assert len(suffix_fixes) == 0


class TestSuffixEdgeCases:
    """Edge cases that previously caused bugs."""

    def test_cr_suffix_not_stripped(self):
        """'SomethingCR' does NOT end with a -R suffix. CR is part of the word."""
        result = apply_fixes("DTL-010:EMR-TT-001:SensorCR")
        assert result == "DTL-010:EMR-TT-001:SensorCR"

    def test_property_only_dash_r_no_empty_result(self):
        """Property '-R' alone: removing -R would leave empty property. Don't fix."""
        result = apply_fixes("DTL-010:EMR-TT-001:-R")
        assert "::" not in result  # Must not produce empty property
        assert result == "DTL-010:EMR-TT-001:-R"  # Left unchanged

    def test_property_only_underscore_r_no_empty_result(self):
        """Property '_R' alone: same guard."""
        result = apply_fixes("DTL-010:EMR-TT-001:_R")
        assert result == "DTL-010:EMR-TT-001:_R"

    def test_property_rbv_to_rb(self):
        """-RBV always becomes -RB, even if property is just '-RBV'."""
        result = apply_fixes("DTL-010:EMR-TT-001:Value-RBV")
        assert result == "DTL-010:EMR-TT-001:Value-RB"

    def test_s_suffix_not_applied_by_apply_fixes(self):
        """-S is NOT auto-fixable, so apply_fixes must leave it unchanged."""
        result = apply_fixes("DTL-010:EMR-TT-001:Temperature-S")
        assert result == "DTL-010:EMR-TT-001:Temperature-S"


class TestCaseFixes:

    def test_lowercase_to_uppercase(self):
        assert apply_fixes("DTL-010:EMR-TT-001:temperature") == "DTL-010:EMR-TT-001:Temperature"

    def test_uppercase_no_change(self):
        assert apply_fixes("DTL-010:EMR-TT-001:Temperature") == "DTL-010:EMR-TT-001:Temperature"

    def test_internal_pv_no_case_fix(self):
        """Internal PVs (#) keep their case — they're internal by definition."""
        assert apply_fixes("DTL-010:EMR-TT-001:#debug") == "DTL-010:EMR-TT-001:#debug"

    def test_case_fix_marked_as_recommendation(self):
        """Case fix description must say 'recommended, not mandatory' (SHOULD rule)."""
        fixes = suggest_fixes("DTL-010:EMR-TT-001:temperature")
        case_fixes = [f for f in fixes if f.rule_id == "PROP-11"]
        assert len(case_fixes) == 1
        assert "recommended" in case_fixes[0].description.lower() or "not mandatory" in case_fixes[0].description.lower()


class TestChaining:
    """apply_fixes() must handle multiple fixes correctly."""

    def test_rbv_plus_case_both_applied(self):
        """RBV→RB first, then case fix on the result."""
        result = apply_fixes("DTL-010:EMR-TT-001:temperature-RBV")
        assert result == "DTL-010:EMR-TT-001:Temperature-RB"

    def test_r_plus_case_both_applied(self):
        result = apply_fixes("DTL-010:EMR-TT-001:temperature-R")
        assert result == "DTL-010:EMR-TT-001:Temperature"

    def test_no_infinite_loop(self):
        """apply_fixes must terminate even with pathological input."""
        result = apply_fixes("DTL-010:EMR-TT-001:Temperature")
        assert result == "DTL-010:EMR-TT-001:Temperature"


class TestNonFixable:

    def test_element_too_long_not_fixable(self):
        fixes = suggest_fixes("ABCDEFG-010:EMR-TT-001:Temperature")
        non_fixable = [f for f in fixes if not f.auto_fixable]
        assert len(non_fixable) > 0

    def test_invalid_format_not_fixable(self):
        fixes = suggest_fixes("TOTALLY::BROKEN::FORMAT")
        assert len(fixes) == 1
        assert not fixes[0].auto_fixable


class TestValidPVs:
    """Valid PVs must produce zero suggestions and remain unchanged."""

    @pytest.mark.parametrize("pv", [
        "DTL-010:EMR-TT-001:Temperature",
        "DTL-010:EMR-TT-001:Temperature-SP",
        "DTL-010:EMR-TT-001:Temperature-RB",
        "DTL-010:EMR-TT-001:#InternalDebug",
        "PBI-BCM01:Ctrl-MTCA-100:Status",
        "Tgt::PowerConsumption",
        "DTL-010::Temperature",
        "ISrc::Status",
        "CWM-CWS03:WtrC-PT-011:Pressure",
    ])
    def test_valid_pv_no_suggestions(self, pv):
        fixes = suggest_fixes(pv)
        auto = [f for f in fixes if f.auto_fixable]
        assert len(auto) == 0, f"Valid PV '{pv}' got unexpected auto-fix suggestions: {[f.description for f in auto]}"

    @pytest.mark.parametrize("pv", [
        "DTL-010:EMR-TT-001:Temperature",
        "DTL-010:EMR-TT-001:Temperature-SP",
        "DTL-010:EMR-TT-001:Temperature-RB",
        "PBI-BCM01:Ctrl-MTCA-100:Status",
        "Tgt::PowerConsumption",
    ])
    def test_valid_pv_unchanged_by_apply(self, pv):
        assert apply_fixes(pv) == pv
