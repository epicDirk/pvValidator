"""Regression test: the hardcoded _builtin_defaults() fallback must not drift
from the YAML for the thresholds the validation engine actually reads.

If the data/ directory is missing (or pyyaml is absent), rule_loader falls back
to _builtin_defaults(). The tool must then validate against the SAME numeric
thresholds as the YAML — otherwise a real install could silently validate
differently. This test fails the moment the two diverge.
"""

from pvValidatorUtils.rule_loader import RuleConfig


def _fallback_config() -> RuleConfig:
    cfg = RuleConfig.__new__(RuleConfig)
    cfg._config = RuleConfig._builtin_defaults()
    return cfg


def test_builtin_defaults_thresholds_match_yaml():
    yaml_cfg = RuleConfig()  # loads the bundled ess-0000757-rev10.yaml
    fallback = _fallback_config()

    assert fallback.max_pv_length == yaml_cfg.max_pv_length
    assert fallback.max_property_length == yaml_cfg.max_property_length
    assert fallback.min_property_length_warn == yaml_cfg.min_property_length_warn
    assert fallback.max_element_length == yaml_cfg.max_element_length
    assert fallback.legacy_prefixes == yaml_cfg.legacy_prefixes


def test_yaml_actually_loaded_not_fallback():
    """Guard that the bundled YAML is present and parsed (not silently degraded)."""
    yaml_cfg = RuleConfig()
    # The YAML carries the full rule set; the fallback only ~6 rules.
    assert len(yaml_cfg.list_rules()) > 10
    assert yaml_cfg.document == "ESS-0000757"
