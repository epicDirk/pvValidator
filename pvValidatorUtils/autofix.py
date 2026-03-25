"""Auto-fix suggestions for PV naming convention violations.

Analyzes validation errors and suggests corrected PV names where possible.
Some violations require human judgment and cannot be auto-fixed.

Design decisions (based on ESS-0000757):
- -S/_S suffix: NOT auto-fixable (might not be a setpoint, needs verification)
- -RBV/_RBV → -RB: Auto-fixable (always a readback, deterministic)
- -R/_R removal: Auto-fixable only if result is non-empty and -R is a suffix
- Case fix: Auto-fixable but marked as SHOULD (recommendation, not mandatory)
- Element length: NOT auto-fixable (abbreviation needs domain knowledge)
"""

from dataclasses import dataclass
from typing import List, Optional

from .parser import PVComponents, parse_pv


@dataclass
class FixSuggestion:
    """A suggested fix for a PV naming violation.

    Attributes:
        original: Original PV name
        suggested: Suggested corrected PV name (empty if no suggestion possible)
        rule_id: Which rule triggered the fix
        description: What was changed and why
        auto_fixable: True if the fix is deterministic (no human judgment needed)
    """
    original: str
    suggested: str
    rule_id: str
    description: str
    auto_fixable: bool = True


def suggest_fixes(pv: str) -> List[FixSuggestion]:
    """Analyze a PV name and suggest fixes for any violations.

    Each suggestion is independent — based on the original PV, not chained.
    Use apply_fixes() for iterative application of auto-fixable suggestions.

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

    fix = _fix_suffix(components)
    if fix:
        suggestions.append(fix)

    fix = _fix_case(components)
    if fix:
        suggestions.append(fix)

    for fix in _check_element_length(components):
        suggestions.append(fix)

    return suggestions


def _fix_suffix(components: PVComponents) -> Optional[FixSuggestion]:
    """Fix incorrect property suffixes per ESS-0000757 §6.2 Rule 9."""
    prop = components.property
    pv = components.raw
    prefix = pv.rsplit(":", 1)[0]

    # -S or _S → suggest -SP (NOT auto-fixable — might not be a setpoint)
    # ESS-0000757 §6.2 Rule 9a: "-S" is forbidden because it resembles a setpoint.
    # But we can't know if the user INTENDED a setpoint without asking.
    if prop.endswith("-S") and not prop.endswith("-SP"):
        return FixSuggestion(
            original=pv,
            suggested=f"{prefix}:{prop[:-2]}-SP",
            rule_id="PROP-SP",
            description='Suffix "-S" resembles incomplete setpoint → "-SP"? (verify intent)',
            auto_fixable=False,
        )
    if prop.endswith("_S") and not prop.endswith("_SP"):
        return FixSuggestion(
            original=pv,
            suggested=f"{prefix}:{prop[:-2]}-SP",
            rule_id="PROP-SP",
            description='Suffix "_S" resembles incomplete setpoint → "-SP"? (verify intent)',
            auto_fixable=False,
        )

    # -RBV or _RBV → -RB (auto-fixable — always means readback)
    if prop.endswith("-RBV"):
        return FixSuggestion(
            original=pv,
            suggested=f"{prefix}:{prop[:-4]}-RB",
            rule_id="PROP-RB",
            description='Suffix "-RBV" → "-RB" (ESS standard)',
        )
    if prop.endswith("_RBV"):
        return FixSuggestion(
            original=pv,
            suggested=f"{prefix}:{prop[:-4]}-RB",
            rule_id="PROP-RB",
            description='Suffix "_RBV" → "-RB" (ESS standard)',
        )

    # -R or _R → remove suffix (auto-fixable, but guard against edge cases)
    # Only match if -R is a standalone suffix (not part of a word like "Sensor-CR")
    # and removal would leave a non-empty property name.
    if prop.endswith("-R") and not prop.endswith("-RB"):
        new_prop = prop[:-2]
        if len(new_prop) > 0 and new_prop[-1].isalnum():
            return FixSuggestion(
                original=pv,
                suggested=f"{prefix}:{new_prop}",
                rule_id="PROP-R",
                description='Removed reading suffix "-R" (readings need no suffix)',
            )
    if prop.endswith("_R") and not prop.endswith("_RB"):
        new_prop = prop[:-2]
        if len(new_prop) > 0 and new_prop[-1].isalnum():
            return FixSuggestion(
                original=pv,
                suggested=f"{prefix}:{new_prop}",
                rule_id="PROP-R",
                description='Removed reading suffix "_R" (readings need no suffix)',
            )

    return None


def _fix_case(components: PVComponents) -> Optional[FixSuggestion]:
    """Suggest uppercase first letter per ESS-0000757 §6.2 Rule 11.

    This is a SHOULD (recommendation), not a SHALL (mandatory).
    """
    prop = components.property
    pv = components.raw

    if not prop or prop.startswith("#"):
        return None  # Internal PVs keep their case

    if prop[0].islower():
        new_prop = prop[0].upper() + prop[1:]
        return FixSuggestion(
            original=pv,
            suggested=f"{pv.rsplit(':', 1)[0]}:{new_prop}",
            rule_id="PROP-11",
            description=f'Uppercase first letter (recommended, not mandatory)',
        )
    return None


def _check_element_length(components: PVComponents) -> List[FixSuggestion]:
    """Flag element length issues (never auto-fixable — needs domain knowledge)."""
    suggestions = []
    for name, value in [
        ("System", components.system),
        ("Subsystem", components.subsystem),
        ("Discipline", components.discipline),
        ("Device", components.device),
    ]:
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
    """Apply all auto-fixable suggestions iteratively.

    Re-evaluates after each applied fix to handle interactions correctly
    (e.g., RBV→RB first, then case fix on the result).

    Returns the original PV if no auto-fixes are applicable.
    """
    current = pv
    for _ in range(5):  # Max iterations to prevent infinite loops
        fixes = suggest_fixes(current)
        applied = False
        for fix in fixes:
            if fix.auto_fixable and fix.suggested and fix.suggested != current:
                current = fix.suggested
                applied = True
                break  # Re-evaluate from scratch after each change
        if not applied:
            break
    return current
