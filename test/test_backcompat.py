"""Backwards-compatibility regression: PVs that were valid before must stay valid.

QA_PLAN claims v1.8.0-valid PVs remain valid in 2.0.0 but never locks it down.
These known-good ESS names must parse and produce no ERROR-level findings
(warnings/info are allowed). If a rule change accidentally rejects one of them,
this test fails.
"""

import pytest

from pvValidatorUtils.parser import parse_pv
from pvValidatorUtils.rules import Severity, check_all_rules

KNOWN_GOOD = [
    "DTL-010:EMR-TT-001:Temperature",
    "DTL-010:EMR-TT-001:Temperature-SP",
    "DTL-010:EMR-TT-001:Temperature-RB",
    "DTL-010:EMR-TT-001:#InternalDebug",
]


@pytest.mark.parametrize("pv", KNOWN_GOOD)
def test_known_good_pv_still_valid(pv):
    components = parse_pv(pv)
    assert components is not None, f"Previously-valid PV no longer parses: {pv}"
    errors = [m for m in check_all_rules(components) if m.severity == Severity.ERROR]
    assert not errors, f"Previously-valid PV now has errors {[m.message for m in errors]}: {pv}"
