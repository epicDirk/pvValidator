"""Tests for the YAML rule configuration loader."""

import pytest

from pvValidatorUtils.rule_loader import RuleConfig


class TestRuleConfigLoading:
    """Test loading rules from YAML."""

    def test_default_config_loads(self):
        config = RuleConfig()
        assert config.document == "ESS-0000757"
        assert config.revision == 10

    def test_metadata(self):
        config = RuleConfig()
        assert "Jorick Lochet" in config.title or config.title != ""
        assert "naming.esss.lu.se" in config.naming_service_url["prod"]

    def test_all_rules_not_empty(self):
        config = RuleConfig()
        assert len(config.all_rules) > 10

    def test_element_rules_present(self):
        config = RuleConfig()
        assert len(config.element_rules) >= 4
        ids = [r["id"] for r in config.element_rules]
        assert "ELEM-1" in ids
        assert "ELEM-6" in ids

    def test_property_rules_present(self):
        config = RuleConfig()
        assert len(config.property_rules) >= 10
        ids = [r["id"] for r in config.property_rules]
        assert "PV-LEN" in ids
        assert "PROP-1" in ids
        assert "PROP-2" in ids
        assert "PROP-SP" in ids
        assert "PROP-RB" in ids

    def test_index_rules_present(self):
        config = RuleConfig()
        assert len(config.index_rules) >= 3

    def test_legacy_rules_present(self):
        config = RuleConfig()
        assert len(config.legacy_rules) >= 1


class TestRuleConfigValues:
    """Test config value accessors."""

    def test_max_pv_length(self):
        config = RuleConfig()
        assert config.max_pv_length == 60

    def test_max_property_length(self):
        config = RuleConfig()
        assert config.max_property_length == 25

    def test_min_property_length_warn(self):
        config = RuleConfig()
        assert config.min_property_length_warn == 4

    def test_max_element_length(self):
        config = RuleConfig()
        assert config.max_element_length == 6

    def test_suffix_exclusions(self):
        config = RuleConfig()
        assert "-SP" in config.property_suffix_exclusions
        assert "-RB" in config.property_suffix_exclusions

    def test_legacy_prefixes(self):
        config = RuleConfig()
        assert "Cmd_" in config.legacy_prefixes
        assert "SP_" in config.legacy_prefixes


class TestRuleConfigLookup:
    """Test rule lookup methods."""

    def test_get_rule_by_id(self):
        config = RuleConfig()
        rule = config.get_rule("PROP-2")
        assert rule is not None
        assert rule["id"] == "PROP-2"
        assert rule["severity"] == "error"

    def test_get_nonexistent_rule(self):
        config = RuleConfig()
        assert config.get_rule("NONEXIST-99") is None

    def test_get_reference(self):
        config = RuleConfig()
        ref = config.get_reference("PROP-2")
        assert "ESS-0000757" in ref
        assert "6.2" in ref

    def test_format_message(self):
        config = RuleConfig()
        msg = config.format_message("PROP-2", "Property exceeds 25 characters")
        assert "[PROP-2]" in msg
        assert "ESS-0000757" in msg
        assert "Property exceeds 25 characters" in msg


class TestRuleConfigFallback:
    """Test fallback when YAML file is missing."""

    def test_missing_file_uses_defaults(self):
        config = RuleConfig("/nonexistent/path/rules.yaml")
        assert config.document == "ESS-0000757"
        assert config.max_pv_length == 60
        assert config.max_property_length == 25
