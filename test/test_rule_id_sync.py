"""Regression test: runtime rule IDs must be explainable via the YAML.

The tool emits ``[RULE-ID]`` tags in validation output and resolves ``--explain
<RULE-ID>`` against the bundled ess-0000757-rev10.yaml. Historically the code
emitted IDs that had no YAML entry (LEGACY vs LEGACY-PREFIX, IDX-STYLE, PROP-EMPTY),
so ``--explain LEGACY`` failed and the ID tags were undocumented.

This test statically extracts the rule IDs that rules.py (ValidationMessage) and
autofix.py (FixSuggestion) can emit and asserts each one exists in the YAML rule
set or in a small, explicitly justified allowlist. It fails the moment a new
runtime ID drifts away from the YAML.

Note: IDs built dynamically (e.g. check_confusable_element picks ELEM-3/ELEM-4 via
a variable) are not string literals and so are not extracted here — those IDs are
in the YAML anyway. The literal-emit sites are where past drift occurred.
"""

import ast
import pathlib

from pvValidatorUtils.rule_loader import RuleConfig

_PKG = pathlib.Path(__file__).resolve().parent.parent / "pvValidatorUtils"

# Synthetic IDs that are intentionally NOT ESS-0000757 YAML rules.
ALLOWLIST = {
    "FMT",  # autofix: generic "invalid format, cannot auto-fix" marker
}


def _string(node):
    return (
        node.value
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        else None
    )


def _emitted_rule_ids(path: pathlib.Path, call_name: str, positional_index=None) -> set:
    """Collect literal rule IDs from ``call_name(...)`` sites in *path*.

    Captures a ``rule_id=`` keyword argument and, for ValidationMessage, the
    3rd positional argument (severity, message, rule_id).
    """
    ids = set()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call) and getattr(node.func, "id", None) == call_name
        ):
            continue
        for kw in node.keywords:
            if kw.arg == "rule_id":
                s = _string(kw.value)
                if s:
                    ids.add(s)
        if positional_index is not None and len(node.args) > positional_index:
            s = _string(node.args[positional_index])
            if s:
                ids.add(s)
    return ids


def _all_emitted_ids() -> set:
    ids = _emitted_rule_ids(_PKG / "rules.py", "ValidationMessage", positional_index=2)
    ids |= _emitted_rule_ids(_PKG / "autofix.py", "FixSuggestion")
    return {i for i in ids if i}


def test_runtime_rule_ids_exist_in_yaml_or_allowlist():
    yaml_ids = set(RuleConfig().list_rules())
    emitted = _all_emitted_ids()
    unknown = {r for r in emitted if r not in yaml_ids and r not in ALLOWLIST}
    assert not unknown, (
        "Runtime rule IDs not found in the YAML or allowlist "
        f"(drift — add them to ess-0000757-rev10.yaml or the allowlist): {sorted(unknown)}"
    )


def test_previously_drifting_ids_are_now_in_yaml():
    """Lock the F13 fix: the three drifted IDs must resolve via the YAML."""
    yaml_ids = set(RuleConfig().list_rules())
    for rid in ("LEGACY-PREFIX", "IDX-STYLE", "PROP-EMPTY", "IDX-LONG"):
        assert rid in yaml_ids, f"{rid} missing from ess-0000757-rev10.yaml"


def test_legacy_id_no_longer_emitted():
    """The bare 'LEGACY' ID was renamed to 'LEGACY-PREFIX' everywhere in code."""
    emitted = _all_emitted_ids()
    assert "LEGACY" not in emitted, "'LEGACY' still emitted — should be 'LEGACY-PREFIX'"
