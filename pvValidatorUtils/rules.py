"""Validation rules for ESS EPICS PV naming convention (ESS-0000757).

Each rule function takes PVComponents and returns a list of ValidationMessages.
Rules are independent, composable, and traceable to ESS-0000757 sections.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from .parser import PVComponents

__all__ = [
    "Severity",
    "ValidationMessage",
    "ValidationResult",
    "check_all_rules",
    "check_property_uniqueness",
    "effective_property_length",
    "normalize_for_confusion",
]

# ---------------------------------------------------------------------------
# Constants (from ESS-0000757)
# ---------------------------------------------------------------------------

MAX_PV_LENGTH = 60
MAX_PROP_LENGTH = 25
MAX_PROP_RECOMMENDED = 20  # SHOULD limit (ESS-0000757 §6.2 Rule 2)
MIN_PROP_LENGTH_WARN = 4
MAX_ELEMENT_LENGTH = 6

# Known short property names from ESS-0000757 Tables 8-9 (valid despite <4 chars)
KNOWN_SHORT_PROPERTIES = frozenset(
    {
        "On",
        "Off",
        "In",
        "Out",
        "Ok",
        "Set",
        "Get",
        "Ack",
        "Low",
        "High",
    }
)

ELEMENT_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")
LEADING_ZERO_REGEX = re.compile(r"0+(?![_A-Za-z-])(?!$)")

LEGACY_PREFIXES = ["Cmd_", "P_", "FB_", "SP_"]
DISALLOWED_CHARS = set("!@$%^&*()+={}[]|\\:;'\"<>,.?/~`")


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class Severity(Enum):
    ERROR = "Error"
    WARNING = "Warning"
    INFO = "Info"


@dataclass
class ValidationMessage:
    """A single validation finding.

    Attributes:
        severity: ERROR, WARNING, or INFO
        message: Human-readable description
        rule_id: Traceability to ESS-0000757 (e.g., 'PROP-2')
    """

    severity: Severity
    message: str
    rule_id: str = ""

    def __str__(self) -> str:
        prefix = f"[{self.rule_id}] " if self.rule_id else ""
        return f"{self.severity.value}: {prefix}{self.message}"


@dataclass
class ValidationResult:
    """Complete validation result for one PV.

    Attributes:
        pv: Original PV string
        format_valid: Whether the PV format is valid
        components: Parsed PV components (None if format invalid)
        messages: List of validation findings
    """

    pv: str
    format_valid: bool
    components: Optional[PVComponents] = None
    messages: List[ValidationMessage] = field(default_factory=list)
    suggestions: list = field(default_factory=list)  # List[FixSuggestion] from autofix

    @property
    def has_errors(self) -> bool:
        return any(m.severity == Severity.ERROR for m in self.messages)

    @property
    def has_warnings(self) -> bool:
        return any(m.severity == Severity.WARNING for m in self.messages)

    @property
    def status(self) -> str:
        if not self.format_valid:
            return "NOT VALID (Wrong Format)"
        if self.has_errors:
            return "NOT VALID"
        if self.has_warnings:
            return "VALID (Warnings)"
        return "VALID"


# ---------------------------------------------------------------------------
# Property rules
# ---------------------------------------------------------------------------


def check_pv_length(components: PVComponents) -> List[ValidationMessage]:
    """ESS-0000757: Total PV max 60 characters."""
    msgs = []
    if len(components.raw) > MAX_PV_LENGTH:
        msgs.append(
            ValidationMessage(
                Severity.ERROR,
                f"The PV is beyond {MAX_PV_LENGTH} characters ({len(components.raw)})",
                "PV-LEN",
            )
        )
    return msgs


def check_property_length(components: PVComponents) -> List[ValidationMessage]:
    """ESS-0000757 §6.2 Rules 2-4: Property length checks.

    Rule 2: SHOULD max 20 chars. Can extend to 25 with justification (SHALL).
    Rule 3: SHOULD min 4 chars.
    Rule 4: Abbreviated forms SHALL have min 4 chars (but known short names
            from ESS-0000757 Tables 8-9 are exempt: On, Off, In, Out, Ok, etc.)
    """
    msgs = []
    prop = components.property
    if not prop:
        msgs.append(
            ValidationMessage(
                Severity.ERROR, "The PV Property is missing", "PROP-EMPTY"
            )
        )
        return msgs

    effective_len = effective_property_length(prop)

    # >25: SHALL violation (hard limit)
    if effective_len > MAX_PROP_LENGTH:
        msgs.append(
            ValidationMessage(
                Severity.ERROR,
                f"The PV Property exceeds {MAX_PROP_LENGTH} characters ({effective_len})",
                "PROP-2",
            )
        )
    # >20 and ≤25: SHOULD violation (recommended limit)
    elif effective_len > MAX_PROP_RECOMMENDED:
        msgs.append(
            ValidationMessage(
                Severity.WARNING,
                f"The PV Property exceeds recommended {MAX_PROP_RECOMMENDED} characters ({effective_len})",
                "PROP-2-WARN",
            )
        )

    # <4 chars: check against known short property names
    if 0 < effective_len < MIN_PROP_LENGTH_WARN:
        # Strip prefix markers for comparison
        clean = prop.lstrip("#")
        if clean not in KNOWN_SHORT_PROPERTIES:
            msgs.append(
                ValidationMessage(
                    Severity.WARNING,
                    f"The PV Property is below {MIN_PROP_LENGTH_WARN} characters ({effective_len})",
                    "PROP-3",
                )
            )

    return msgs


def effective_property_length(prop: str) -> int:
    """Property length excluding -SP/-RB suffix (ESS-0000757 §6.2 Rule 9)."""
    for suffix in ("-SP", "-RB"):
        if prop.endswith(suffix):
            return len(prop) - len(suffix)
    return len(prop)


def check_property_suffix(components: PVComponents) -> List[ValidationMessage]:
    """ESS-0000757 §6.2 Rule 9: Setpoint -SP, Readback -RB."""
    msgs = []
    prop = components.property

    if prop.endswith("-S") or prop.endswith("_S"):
        msgs.append(
            ValidationMessage(
                Severity.ERROR,
                "The PV Property for a Setpoint value should end with -SP",
                "PROP-SP",
            )
        )

    if prop.endswith("-R") or prop.endswith("_R"):
        msgs.append(
            ValidationMessage(
                Severity.ERROR,
                "The PV Property for a Reading value should not contain any suffix",
                "PROP-R",
            )
        )

    if prop.endswith("-RBV") or prop.endswith("_RBV"):
        msgs.append(
            ValidationMessage(
                Severity.ERROR,
                "The PV Property for a Readback value should end with -RB",
                "PROP-RB",
            )
        )

    return msgs


def check_property_characters(components: PVComponents) -> List[ValidationMessage]:
    """ESS-0000757 §6.2 Rule 11: Alphanumeric, starts with letter."""
    msgs: List[ValidationMessage] = []
    prop = components.property
    if not prop:
        return msgs

    # Internal PVs start with #
    if prop.startswith("#"):
        msgs.append(
            ValidationMessage(Severity.INFO, 'The PV is an "Internal PV"', "PROP-INT")
        )
        return msgs

    # Must start with letter
    if prop[0].isdigit() or prop[0] in DISALLOWED_CHARS or prop[0] in ("_", "-"):
        msgs.append(
            ValidationMessage(
                Severity.ERROR,
                "The PV Property does not start alphabetical",
                "PROP-11",
            )
        )

    # Should start with uppercase
    if prop[0].islower():
        msgs.append(
            ValidationMessage(
                Severity.WARNING,
                "The PV Property does not start in upper case",
                "PROP-11-CASE",
            )
        )

    # No disallowed characters
    if any(c in DISALLOWED_CHARS for c in prop):
        msgs.append(
            ValidationMessage(
                Severity.ERROR,
                "The PV Property contains not allowed character(s)",
                "PROP-11-CHAR",
            )
        )

    # Hash in wrong position
    if "#" in prop and not prop.startswith("#"):
        msgs.append(
            ValidationMessage(
                Severity.ERROR,
                "The PV Property contains the # character in not allowed position",
                "PROP-11-HASH",
            )
        )

    return msgs


def check_element_lengths(components: PVComponents) -> List[ValidationMessage]:
    """ESS-0000757 §3 Rule 6: Sys/Sub/Dis/Dev max 6 characters.

    Exception: Target Station (Tgt) may use longer subsystem codes
    per ESS-0000757 Annex B, Section 9.2.
    """
    msgs = []
    elements = [
        ("System", components.system),
        ("Subsystem", components.subsystem),
        ("Discipline", components.discipline),
        ("Device", components.device),
    ]
    for name, value in elements:
        if value and len(value) > MAX_ELEMENT_LENGTH:
            # Target Station exception for subsystem (Annex B)
            if name == "Subsystem" and components.system == "Tgt":
                msgs.append(
                    ValidationMessage(
                        Severity.INFO,
                        f'Target Station subsystem "{value}" exceeds {MAX_ELEMENT_LENGTH} characters (allowed per Annex B)',
                        "EXC-TGT",
                    )
                )
            else:
                msgs.append(
                    ValidationMessage(
                        Severity.ERROR,
                        f'The {name} "{value}" exceeds {MAX_ELEMENT_LENGTH} characters ({len(value)})',
                        "ELEM-6",
                    )
                )
    return msgs


def check_element_characters(components: PVComponents) -> List[ValidationMessage]:
    """ESS-0000757 §3 Rules 1-2: Alphanumeric, starts with letter.

    Note: Subsystems may start with digits (e.g., '010' for section numbers)
    per established ESS practice (DTL-010, HBL-010, etc.). The alphanumeric
    rule still applies but the "starts with letter" rule is relaxed for subsystems.
    """
    msgs = []
    elements = [
        ("System", components.system, True),  # must start with letter
        (
            "Subsystem",
            components.subsystem,
            False,
        ),  # may start with digit (section numbers)
        ("Discipline", components.discipline, True),
        ("Device", components.device, True),
    ]
    for name, value, require_alpha_start in elements:
        if not value:
            continue
        if not value.isalnum():
            msgs.append(
                ValidationMessage(
                    Severity.ERROR,
                    f'The {name} "{value}" contains non-alphanumeric characters',
                    "ELEM-1",
                )
            )
        elif require_alpha_start and not value[0].isalpha():
            msgs.append(
                ValidationMessage(
                    Severity.ERROR,
                    f'The {name} "{value}" must start with a letter',
                    "ELEM-2",
                )
            )
    return msgs


def check_device_index(components: PVComponents) -> List[ValidationMessage]:
    """ESS-0000757 §5.2: Index validation (Scientific or P&ID style)."""
    msgs: List[ValidationMessage] = []
    idx = components.index

    if components.is_high_level:
        return msgs  # No index for high-level PVs

    if not idx:
        msgs.append(
            ValidationMessage(
                Severity.ERROR,
                "Device index is missing",
                "IDX-MANDATORY",
            )
        )
        return msgs

    # Scientific style: purely numeric, 1-4 digits
    scientific = re.compile(r"^\d{1,4}$")
    # P&ID style: 3 numeric digits + optional 1-3 lowercase letters
    pid = re.compile(r"^\d{3}[a-z]{0,3}$")
    # Extended: up to 4 digits (special cases)
    extended = re.compile(r"^\d{1,6}$")

    if not (scientific.match(idx) or pid.match(idx) or extended.match(idx)):
        msgs.append(
            ValidationMessage(
                Severity.WARNING,
                f'Index "{idx}" does not follow Scientific or P&ID style',
                "IDX-STYLE",
            )
        )

    if len(idx) > 6:
        msgs.append(
            ValidationMessage(
                Severity.ERROR,
                f'Index "{idx}" exceeds 6 characters',
                "IDX-LEN",
            )
        )

    return msgs


def check_legacy_prefix(components: PVComponents) -> List[ValidationMessage]:
    """ESS-0000757 Annex C: Warn on legacy property prefixes."""
    msgs = []
    for prefix in LEGACY_PREFIXES:
        if components.property.startswith(prefix):
            msgs.append(
                ValidationMessage(
                    Severity.WARNING,
                    f'Property uses legacy prefix "{prefix}" (accepted but discouraged)',
                    "LEGACY",
                )
            )
            break
    return msgs


def check_legacy_index(components: PVComponents) -> List[ValidationMessage]:
    """ESS-0000757 Annex C: 5-digit index is legacy for Cryo/Vacuum."""
    if components.is_high_level or not components.index:
        return []
    if components.discipline in ("Cryo", "Vac") and len(components.index) > 4:
        return [
            ValidationMessage(
                Severity.WARNING,
                f"5-digit index is legacy for {components.discipline} (use max 4 digits)",
                "LEGACY-5DIGIT",
            )
        ]
    return []


def check_pascal_case(components: PVComponents) -> List[ValidationMessage]:
    """ESS-0000757 §6.2 Rule 5: Properties SHOULD use PascalCase."""
    prop = components.property
    if not prop or prop.startswith("#"):
        return []
    # Strip standard suffixes before checking
    clean = prop
    for suffix in ("-SP", "-RB"):
        if clean.endswith(suffix):
            clean = clean[: -len(suffix)]
            break
    if len(clean) <= 4 or clean in KNOWN_SHORT_PROPERTIES:
        return []
    if clean.isupper() or clean.islower():
        return [
            ValidationMessage(
                Severity.WARNING,
                "Property should use PascalCase for multi-word names",
                "PROP-5",
            )
        ]
    return []


MTCA_DEVICES = frozenset({"MTCA", "CPU", "EVR"})


def check_mtca_naming(components: PVComponents) -> List[ValidationMessage]:
    """ESS-0000757 Annex A: MTCA controller index must be 3 digits."""
    if components.discipline != "Ctrl" or components.device not in MTCA_DEVICES:
        return []
    if components.index and not re.match(r"^\d{3}$", components.index):
        return [
            ValidationMessage(
                Severity.WARNING,
                "MTCA index should be 3 digits (system + counter)",
                "EXC-MTCA",
            )
        ]
    return []


# ---------------------------------------------------------------------------
# Confusable character detection (O(n) via normalization)
# ---------------------------------------------------------------------------


def normalize_for_confusion(prop: str) -> str:
    """Normalize a property name for confusable character detection.

    Maps: I→1, l→1, O→0, VV→W, strips leading zeros.
    Result is lowercase for case-insensitive comparison.
    """
    result = prop.lower()
    result = result.replace("l", "1").replace("i", "1")
    result = result.replace("o", "0")
    result = result.replace("vv", "w")
    result = LEADING_ZERO_REGEX.sub("@", result)
    return result


def check_property_uniqueness(
    device_key: str, properties: List[str]
) -> Dict[str, List[ValidationMessage]]:
    """Check property uniqueness within a device (O(n) algorithm).

    Args:
        device_key: The device part of the PV (before the last colon)
        properties: List of property names for this device

    Returns:
        Dict mapping PV name → list of ValidationMessages
    """
    msgs: Dict[str, List[ValidationMessage]] = {}
    seen: Dict[str, str] = {}  # normalized → first property
    errs = "The PV Property is not unique"

    for prop in properties:
        pv = f"{device_key}:{prop}"
        if pv not in msgs:
            msgs[pv] = []

        normalized = normalize_for_confusion(prop)
        if normalized in seen:
            existing_prop = seen[normalized]
            existing_pv = f"{device_key}:{existing_prop}"

            # Determine the type of confusion
            if prop == existing_prop:
                issue = "duplication issue"
            elif prop.lower() == existing_prop.lower():
                issue = f"case issue, check {existing_pv}"
            elif (
                prop.replace("O", "0") == existing_prop
                or prop.replace("0", "O") == existing_prop
            ):
                issue = f"0 O issue, check {existing_pv}"
            elif (
                prop.replace("VV", "W") == existing_prop
                or prop.replace("W", "VV") == existing_prop
            ):
                issue = f"VV W issue, check {existing_pv}"
            elif (
                prop.replace("1", "I") == existing_prop
                or prop.replace("I", "1") == existing_prop
                or prop.replace("1", "l") == existing_prop
                or prop.replace("l", "1") == existing_prop
                or prop.replace("I", "l") == existing_prop
                or prop.replace("l", "I") == existing_prop
            ):
                issue = f"1 I l issue, check {existing_pv}"
            else:
                issue = f"leading zero or combined issue, check {existing_pv}"

            msgs[pv].append(
                ValidationMessage(
                    Severity.ERROR,
                    f"{errs} ({issue})",
                    "PROP-1",
                )
            )
            # Also flag the first occurrence
            if existing_pv not in msgs:
                msgs[existing_pv] = []
            conflict_msg = ValidationMessage(
                Severity.ERROR,
                f"{errs} ({issue.replace(existing_pv, pv)})",
                "PROP-1",
            )
            if not any(
                m.rule_id == "PROP-1" and pv in m.message for m in msgs[existing_pv]
            ):
                msgs[existing_pv].append(conflict_msg)
        else:
            seen[normalized] = prop

    return msgs


# ---------------------------------------------------------------------------
# Rule runner
# ---------------------------------------------------------------------------

# All single-PV rule functions
SINGLE_PV_RULES = [
    check_pv_length,
    check_property_length,
    check_property_suffix,
    check_property_characters,
    check_element_lengths,
    check_element_characters,
    check_device_index,
    check_legacy_prefix,
    check_legacy_index,
    check_pascal_case,
    check_mtca_naming,
]


def check_all_rules(components: PVComponents) -> List[ValidationMessage]:
    """Run all single-PV validation rules.

    Does NOT include uniqueness checks (those need the full PV list).
    """
    msgs = []
    for rule_fn in SINGLE_PV_RULES:
        msgs.extend(rule_fn(components))
    return msgs
