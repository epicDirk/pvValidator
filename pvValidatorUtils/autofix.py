"""Auto-fix suggestions for PV naming convention violations.

Analyzes validation errors and suggests corrected PV names where possible.
Some violations require human judgment and cannot be auto-fixed.
"""

import re
from dataclasses import dataclass
from typing import List, Optional

from .parser import PVComponents, parse_pv
from .rules import Severity, ValidationMessage, check_all_rules


@dataclass
class FixSuggestion:
    """A suggested fix for a PV naming violation.

    Attributes:
        original: Original PV name
        suggested: Suggested corrected PV name
        rule_id: Which rule triggered the fix
        description: What was changed
        auto_fixable: True if the fix is deterministic (no human judgment needed)
    """
    original: str
    suggested: str
    rule_id: str
    description: str
    auto_fixable: bool = True


def suggest_fixes(pv: str) -> List[FixSuggestion]:
    """Analyze a PV name and suggest fixes for any violations.

    Args:
        pv: Original PV name string

    Returns:
        List of fix suggestions. Empty if no fixes needed or possible.
    """
    components = parse_pv(pv)
    if components is None:
        return [FixSuggestion(
            original=pv,
            suggested="",
            rule_id="FMT",
            description="Invalid PV format — cannot auto-fix (check colons and separators)",
            auto_fixable=False,
        )]

    suggestions = []

    # Suffix fixes
    fix = _fix_suffix(components)
    if fix:
        suggestions.append(fix)

    # Case fix (always based on ORIGINAL components, not on suffix-fix result,
    # because the suffix fix might not be auto-fixable and the user might not apply it)
    fix = _fix_case(components)
    if fix:
        suggestions.append(fix)

    # Element length (not auto-fixable)
    if components:
        for fix in _check_element_length(components):
            suggestions.append(fix)

    return suggestions


def _fix_suffix(components: PVComponents) -> Optional[FixSuggestion]:
    """Fix incorrect property suffixes."""
    prop = components.property
    pv = components.raw

    # -S or _S → suggest -SP (but NOT auto-fixable — might not be a setpoint)
    # ESS-0000757 §6.2 Rule 9a forbids -S/_S because it looks like a setpoint,
    # but the property might not actually BE a setpoint. Needs human judgment.
    if prop.endswith("-S") and not prop.endswith("-SP"):
        new_prop = prop[:-2] + "-SP"
        return FixSuggestion(
            original=pv,
            suggested=pv.rsplit(":", 1)[0] + ":" + new_prop,
            rule_id="PROP-SP",
            description=f'Suffix "-S" looks like incomplete setpoint → "-SP"? (verify: is this actually a setpoint?)',
            auto_fixable=False,
        )
    if prop.endswith("_S") and not prop.endswith("_SP"):
        new_prop = prop[:-2] + "-SP"
        return FixSuggestion(
            original=pv,
            suggested=pv.rsplit(":", 1)[0] + ":" + new_prop,
            rule_id="PROP-SP",
            description=f'Suffix "_S" looks like incomplete setpoint → "-SP"? (verify: is this actually a setpoint?)',
            auto_fixable=False,
        )

    # -RBV or _RBV → -RB
    if prop.endswith("-RBV"):
        new_prop = prop[:-4] + "-RB"
        return FixSuggestion(
            original=pv,
            suggested=pv.rsplit(":", 1)[0] + ":" + new_prop,
            rule_id="PROP-RB",
            description=f'Suffix "-RBV" → "-RB"',
        )
    if prop.endswith("_RBV"):
        new_prop = prop[:-4] + "-RB"
        return FixSuggestion(
            original=pv,
            suggested=pv.rsplit(":", 1)[0] + ":" + new_prop,
            rule_id="PROP-RB",
            description=f'Suffix "_RBV" → "-RB"',
        )

    # -R or _R → remove suffix
    if prop.endswith("-R") and not prop.endswith("-RB"):
        new_prop = prop[:-2]
        return FixSuggestion(
            original=pv,
            suggested=pv.rsplit(":", 1)[0] + ":" + new_prop,
            rule_id="PROP-R",
            description=f'Removed reading suffix "-R"',
        )
    if prop.endswith("_R") and not prop.endswith("_RB"):
        new_prop = prop[:-2]
        return FixSuggestion(
            original=pv,
            suggested=pv.rsplit(":", 1)[0] + ":" + new_prop,
            rule_id="PROP-R",
            description=f'Removed reading suffix "_R"',
        )

    return None


def _fix_case(components: PVComponents) -> Optional[FixSuggestion]:
    """Suggest uppercase first letter (SHOULD rule, not SHALL)."""
    prop = components.property
    pv = components.raw

    # ESS-0000757 §6.2 Rule 11: Property SHOULD start in upper case.
    # This is a recommendation (SHOULD), not mandatory (SHALL).
    if prop and prop[0].islower() and not prop.startswith("#"):
        new_prop = prop[0].upper() + prop[1:]
        return FixSuggestion(
            original=pv,
            suggested=pv.rsplit(":", 1)[0] + ":" + new_prop,
            rule_id="PROP-11",
            description=f'Uppercase first letter (recommended, not mandatory): "{prop[0]}" → "{prop[0].upper()}"',
        )
    return None


def _check_element_length(components: PVComponents) -> List[FixSuggestion]:
    """Flag element length issues (not auto-fixable)."""
    suggestions = []
    elements = [
        ("System", components.system),
        ("Subsystem", components.subsystem),
        ("Discipline", components.discipline),
        ("Device", components.device),
    ]
    for name, value in elements:
        if value and len(value) > 6:
            suggestions.append(FixSuggestion(
                original=components.raw,
                suggested="",
                rule_id="ELEM-6",
                description=f'{name} "{value}" exceeds 6 chars — needs human decision',
                auto_fixable=False,
            ))
    return suggestions


def apply_fixes(pv: str) -> str:
    """Apply all auto-fixable suggestions and return the corrected PV.

    Only applies fixes where auto_fixable=True.
    Returns the original PV if no auto-fixes are applicable.
    """
    current = pv
    for fix in suggest_fixes(pv):
        if fix.auto_fixable and fix.suggested:
            current = fix.suggested
    return current
