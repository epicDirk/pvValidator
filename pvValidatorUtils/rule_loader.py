"""YAML-based rule configuration loader for pvValidator.

Loads validation rules from YAML files, enabling:
- Rule updates without code changes (new ESS-0000757 revisions)
- Traceability from validation output to document sections
- Configurable severity levels
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("pvvalidator")

try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False


# Default rule file path
DEFAULT_RULES_PATH = Path(__file__).parent / "data" / "rules" / "ess-0000757-rev10.yaml"


class RuleConfig:
    """Configuration loaded from a YAML rules file.

    Provides typed access to validation rules with their metadata,
    severity levels, and document references.

    Usage:
        config = RuleConfig()  # loads default ESS-0000757 Rev 10
        config = RuleConfig("/path/to/custom-rules.yaml")

        for rule in config.property_rules:
            print(rule["id"], rule["severity"], rule["reference"])
    """

    def __init__(self, config_path: Optional[str] = None):
        if not HAS_YAML:
            logger.warning("pyyaml not installed — using built-in defaults")
            self._config = self._builtin_defaults()
            return

        path = Path(config_path) if config_path else DEFAULT_RULES_PATH
        if not path.exists():
            logger.warning(f"Rules file not found: {path} — using built-in defaults")
            self._config = self._builtin_defaults()
            return

        with open(path, encoding="utf-8") as f:
            self._config = yaml.safe_load(f)

        logger.info(f"Loaded rules: {self.document} Rev {self.revision}")

    # -----------------------------------------------------------------
    # Metadata
    # -----------------------------------------------------------------

    @property
    def document(self) -> str:
        return self._config.get("metadata", {}).get("document", "ESS-0000757")

    @property
    def revision(self) -> int:
        return self._config.get("metadata", {}).get("revision", 10)

    @property
    def title(self) -> str:
        return self._config.get("metadata", {}).get("title", "")

    @property
    def naming_service_url(self) -> Dict[str, str]:
        return self._config.get("metadata", {}).get(
            "naming_service",
            {
                "prod": "https://naming.esss.lu.se/",
                "test": "https://naming-test-01.cslab.esss.lu.se/",
            },
        )

    # -----------------------------------------------------------------
    # Rule accessors
    # -----------------------------------------------------------------

    @property
    def format_rules(self) -> Dict[str, Any]:
        return self._config.get("format", {})

    @property
    def element_rules(self) -> List[Dict]:
        return self._config.get("elements", [])

    @property
    def index_rules(self) -> List[Dict]:
        return self._config.get("index", [])

    @property
    def property_rules(self) -> List[Dict]:
        return self._config.get("property", [])

    @property
    def legacy_rules(self) -> List[Dict]:
        return self._config.get("legacy", [])

    @property
    def exception_rules(self) -> List[Dict]:
        return self._config.get("exceptions", [])

    @property
    def all_rules(self) -> List[Dict]:
        """All rules flattened into a single list."""
        rules = []
        rules.extend(self.element_rules)
        rules.extend(self.index_rules)
        rules.extend(self.property_rules)
        rules.extend(self.legacy_rules)
        rules.extend(self.exception_rules)
        return rules

    # -----------------------------------------------------------------
    # Lookup
    # -----------------------------------------------------------------

    def get_rule(self, rule_id: str) -> Optional[Dict]:
        """Find a rule by its ID (e.g., 'PROP-2')."""
        for rule in self.all_rules:
            if rule.get("id") == rule_id:
                return rule
        return None

    def list_rules(self) -> List[str]:
        """Return all rule IDs."""
        return [r.get("id", "") for r in self.all_rules if r.get("id")]

    def get_reference(self, rule_id: str) -> str:
        """Get the ESS-0000757 section reference for a rule ID."""
        rule = self.get_rule(rule_id)
        if rule:
            return f"{self.document} {rule.get('reference', '')}"
        return ""

    def format_message(self, rule_id: str, message: str) -> str:
        """Format a validation message with rule ID and reference.

        Example: 'Error [PROP-2]: Property exceeds 25 characters [ESS-0000757 §6.2]'
        """
        ref = self.get_reference(rule_id)
        ref_str = f" [{ref}]" if ref else ""
        id_str = f"[{rule_id}] " if rule_id else ""
        return f"{id_str}{message}{ref_str}"

    # -----------------------------------------------------------------
    # Config values (used by validation engine)
    # -----------------------------------------------------------------

    @property
    def max_pv_length(self) -> int:
        for rule in self.property_rules:
            if rule.get("id") == "PV-LEN":
                return rule.get("value", 60)
        return 60

    @property
    def max_property_length(self) -> int:
        for rule in self.property_rules:
            if rule.get("id") == "PROP-2":
                return rule.get("value", 25)
        return 25

    @property
    def min_property_length_warn(self) -> int:
        for rule in self.property_rules:
            if rule.get("id") == "PROP-3":
                return rule.get("value", 4)
        return 4

    @property
    def max_element_length(self) -> int:
        for rule in self.element_rules:
            if rule.get("id") == "ELEM-6":
                return rule.get("value", 6)
        return 6

    @property
    def property_suffix_exclusions(self) -> List[str]:
        for rule in self.property_rules:
            if rule.get("id") == "PROP-2":
                return rule.get("exclude_suffixes", ["-SP", "-RB"])
        return ["-SP", "-RB"]

    @property
    def legacy_prefixes(self) -> List[str]:
        for rule in self.legacy_rules:
            if rule.get("id") == "LEGACY-PREFIX":
                return rule.get("prefixes", ["Cmd_", "P_", "FB_", "SP_"])
        return ["Cmd_", "P_", "FB_", "SP_"]

    @property
    def disallowed_chars(self) -> str:
        for rule in self.property_rules:
            if rule.get("id") == "PROP-11-CHAR":
                return rule.get("disallowed", "!@$%^&*()+={}[]|\\:;'\"<>,.?/~`")
        return "!@$%^&*()+={}[]|\\:;'\"<>,.?/~`"

    # -----------------------------------------------------------------
    # Built-in defaults (when YAML not available)
    # -----------------------------------------------------------------

    @staticmethod
    def _builtin_defaults() -> Dict:
        """Hardcoded fallback when pyyaml is not installed."""
        return {
            "metadata": {
                "document": "ESS-0000757",
                "revision": 10,
                "naming_service": {
                    "prod": "https://naming.esss.lu.se/",
                    "test": "https://naming-test-01.cslab.esss.lu.se/",
                },
            },
            "elements": [
                {
                    "id": "ELEM-6",
                    "check": "max_length",
                    "value": 6,
                    "severity": "error",
                },
            ],
            "index": [],
            "property": [
                {
                    "id": "PV-LEN",
                    "check": "pv_max_length",
                    "value": 60,
                    "severity": "error",
                },
                {
                    "id": "PROP-2",
                    "check": "max_length",
                    "value": 25,
                    "exclude_suffixes": ["-SP", "-RB"],
                    "severity": "error",
                },
                {
                    "id": "PROP-3",
                    "check": "min_length",
                    "value": 4,
                    "severity": "warning",
                },
            ],
            "legacy": [
                {
                    "id": "LEGACY-PREFIX",
                    "prefixes": ["Cmd_", "P_", "FB_", "SP_"],
                    "severity": "warning",
                },
            ],
            "exceptions": [],
        }
