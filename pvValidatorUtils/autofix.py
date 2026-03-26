"""Auto-fix suggestions for PV naming convention violations.

Analyzes validation errors and suggests corrected PV names where possible.
Some violations require human judgment and cannot be auto-fixed.

Design decisions (based on ESS-0000757):
- -S/_S suffix: NOT auto-fixable (might not be a setpoint, needs verification)
- -RBV/_RBV → -RB: Auto-fixable (always a readback, deterministic)
- -R/_R removal: Auto-fixable only if result is non-empty and -R is a suffix
- Case fix: Auto-fixable but marked as SHOULD (recommendation, not mandatory)
- Element length: NOT auto-fixable (abbreviation needs domain knowledge)
- Legacy prefix: Auto-fixable (deterministic removal of Cmd_, P_, FB_, SP_)
- MTCA index: Auto-fixable (zero-pad to 3 digits)

Self-verification (Semgrep pattern): Every auto-fixable suggestion is validated
before being shown. If the fix would introduce a new ERROR, it is downgraded
to a manual suggestion. This prevents silent severity downgrades.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from .parser import PVComponents, parse_pv


class Applicability(Enum):
    """How safe it is to apply this fix automatically.

    Modeled after Ruff (Safe/Unsafe) and Clippy (MachineApplicable/MaybeIncorrect).
    """
    SAFE = "safe"            # Deterministic, zero semantic risk. Applied with --fix.
    SUGGESTED = "suggested"  # Probably correct, verify. Applied with --fix --unsafe.
    TEMPLATE = "template"    # Has placeholders. Display only.
    MANUAL = "manual"        # Cannot auto-fix. Needs human decision.


@dataclass
class FixSuggestion:
    """A suggested fix for a PV naming violation.

    Attributes:
        original: Original PV name
        suggested: Suggested corrected PV name (empty if no suggestion possible)
        rule_id: Which rule triggered the fix
        description: What was changed and why
        applicability: How safe the fix is to apply automatically
        auto_fixable: True if applicability is SAFE (convenience property)
        verified: True if the suggestion was self-verified against validation rules
    """
    original: str
    suggested: str
    rule_id: str
    description: str
    applicability: Applicability = Applicability.SAFE
    verified: bool = False

    @property
    def auto_fixable(self) -> bool:
        return self.applicability == Applicability.SAFE


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
            applicability=Applicability.MANUAL,
        )]

    suggestions = []

    fix = _fix_suffix(components)
    if fix:
        suggestions.append(fix)

    fix = _fix_case(components)
    if fix:
        suggestions.append(fix)

    fix = _fix_legacy_prefix(components)
    if fix:
        suggestions.append(fix)

    fix = _fix_mtca_index(components)
    if fix:
        suggestions.append(fix)

    for fix in _check_element_length(components):
        suggestions.append(fix)

    # Self-verification: validate every auto-fixable suggestion
    _verify_suggestions(suggestions)

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
            applicability=Applicability.SUGGESTED,
        )
    if prop.endswith("_S") and not prop.endswith("_SP"):
        return FixSuggestion(
            original=pv,
            suggested=f"{prefix}:{prop[:-2]}-SP",
            rule_id="PROP-SP",
            description='Suffix "_S" resembles incomplete setpoint → "-SP"? (verify intent)',
            applicability=Applicability.SUGGESTED,
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
                applicability=Applicability.MANUAL,
            ))
    return suggestions


LEGACY_PREFIXES = ["Cmd_", "P_", "FB_", "SP_"]


def _fix_legacy_prefix(components: PVComponents) -> Optional[FixSuggestion]:
    """Strip legacy property prefixes per ESS-0000757 Annex C."""
    prop = components.property
    pv = components.raw
    prefix_part = pv.rsplit(":", 1)[0]

    for legacy in LEGACY_PREFIXES:
        if prop.startswith(legacy):
            new_prop = prop[len(legacy):]
            if new_prop:
                return FixSuggestion(
                    original=pv,
                    suggested=f"{prefix_part}:{new_prop}",
                    rule_id="LEGACY",
                    description=f'Removed legacy prefix "{legacy}" (accepted but discouraged)',
                    applicability=Applicability.SAFE,
                )
    return None


def _fix_mtca_index(components: PVComponents) -> Optional[FixSuggestion]:
    """Zero-pad MTCA controller index to 3 digits per ESS-0000757 Annex A."""
    import re as _re
    if components.discipline != "Ctrl" or components.device not in ("MTCA", "CPU", "EVR"):
        return None
    idx = components.index
    if not idx or _re.match(r"^\d{3}$", idx):
        return None  # already correct or missing
    if idx.isdigit() and len(idx) < 3:
        new_idx = idx.zfill(3)
        pv = components.raw
        return FixSuggestion(
            original=pv,
            suggested=pv.replace(f"-{idx}:", f"-{new_idx}:"),
            rule_id="EXC-MTCA",
            description=f'Zero-padded MTCA index "{idx}" → "{new_idx}" (3-digit format)',
            applicability=Applicability.SAFE,
        )
    return None


def _verify_suggestions(suggestions: List[FixSuggestion]) -> None:
    """Self-verify: check that auto-fixable suggestions don't introduce new errors.

    Inspired by Semgrep's fix verification pattern. If a suggested fix would
    fail validation, downgrade it from SAFE/SUGGESTED to MANUAL.
    """
    from .rules import Severity, check_all_rules  # late import to avoid circular

    for s in suggestions:
        if s.applicability in (Applicability.SAFE, Applicability.SUGGESTED) and s.suggested:
            components = parse_pv(s.suggested)
            if components is None:
                # Fix produces unparseable PV — definitely broken
                s.applicability = Applicability.MANUAL
                s.description += " (fix produces invalid format — manual review needed)"
                s.verified = True
                continue
            msgs = check_all_rules(components)
            errors = [m for m in msgs if m.severity == Severity.ERROR]
            if errors:
                # Fix introduces new errors — downgrade
                s.applicability = Applicability.MANUAL
                s.description += f" (fix introduces {len(errors)} new issue(s) — manual review needed)"
            s.verified = True


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
