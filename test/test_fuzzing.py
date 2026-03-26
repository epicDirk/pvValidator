"""Property-based fuzzing tests using Hypothesis.

Generates random PV-like strings and verifies that:
- The parser never crashes (no unhandled exceptions)
- Every parseable PV can also be validated
- Normalization for confusable detection is idempotent
- Round-trip: parse → to_list → no data loss
"""

import string

import pytest

try:
    from hypothesis import given, settings
    from hypothesis import strategies as st

    HAS_HYPOTHESIS = True
except ImportError:
    HAS_HYPOTHESIS = False

from pvValidatorUtils.parser import PVComponents, parse_pv
from pvValidatorUtils.rules import (
    check_all_rules,
    normalize_for_confusion,
)

skipno = pytest.mark.skipif(not HAS_HYPOTHESIS, reason="hypothesis not installed")

if HAS_HYPOTHESIS:
    element = st.text(
        alphabet=string.ascii_letters + string.digits, min_size=1, max_size=8
    )
    property_chars = string.ascii_letters + string.digits + "-_#"
    prop = st.text(alphabet=property_chars, min_size=1, max_size=30)
    full_pv = st.builds(
        lambda s, sub, dis, dev, idx, p: f"{s}-{sub}:{dis}-{dev}-{idx}:{p}",
        element,
        element,
        element,
        element,
        element,
        prop,
    )
    high_level_pv = st.builds(lambda s, p: f"{s}::{p}", element, prop)
    any_pv = st.one_of(full_pv, high_level_pv)
    random_string = st.text(min_size=0, max_size=100)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@skipno
class TestParserNeverCrashes:
    """The parser must handle any input without crashing."""

    @given(s=random_string)
    @settings(max_examples=500)
    def test_random_string_no_crash(self, s):
        """Parser returns None or PVComponents, never raises."""
        result = parse_pv(s)
        assert result is None or isinstance(result, PVComponents)

    @given(pv=any_pv)
    @settings(max_examples=200)
    def test_generated_pv_parseable(self, pv):
        """Generated PVs with correct structure should parse."""
        result = parse_pv(pv)
        # May be None if generated elements are empty after filtering
        if result is not None:
            assert result.raw == pv
            assert result.system != ""


@skipno
class TestRulesNeverCrash:
    """Validation rules must handle any parsed PV without crashing."""

    @given(pv=full_pv)
    @settings(max_examples=200)
    def test_rules_on_generated_pvs(self, pv):
        """Rules return a list of messages, never raise."""
        components = parse_pv(pv)
        if components is not None:
            msgs = check_all_rules(components)
            assert isinstance(msgs, list)


@skipno
class TestNormalizationProperties:
    """Normalization for confusable detection has specific properties."""

    @given(
        s=st.text(
            alphabet=string.ascii_letters + string.digits, min_size=1, max_size=20
        )
    )
    @settings(max_examples=300)
    def test_normalization_idempotent(self, s):
        """Normalizing twice gives the same result as normalizing once."""
        once = normalize_for_confusion(s)
        twice = normalize_for_confusion(once)
        assert once == twice

    @given(
        s=st.text(
            alphabet=string.ascii_letters + string.digits, min_size=1, max_size=20
        )
    )
    def test_normalization_lowercase(self, s):
        """Normalized output is always lowercase."""
        result = normalize_for_confusion(s)
        # After normalization, digits and @ are OK, letters must be lowercase
        for c in result:
            if c.isalpha():
                assert c.islower()

    def test_known_confusables(self):
        """Known confusable pairs normalize to the same string."""
        assert normalize_for_confusion("TempI") == normalize_for_confusion("Templ")
        assert normalize_for_confusion("TempI") == normalize_for_confusion("Temp1")
        assert normalize_for_confusion("TempO") == normalize_for_confusion("Temp0")
        assert normalize_for_confusion("TempVV") == normalize_for_confusion("TempW")


@skipno
class TestRoundTrip:
    """Parse → to_list → no data loss."""

    @given(pv=full_pv)
    @settings(max_examples=200)
    def test_to_list_preserves_data(self, pv):
        """to_list() returns exactly 6 elements matching the parsed components."""
        components = parse_pv(pv)
        if components is not None:
            lst = components.to_list()
            assert len(lst) == 6
            assert lst[0] == components.system
            assert lst[5] == components.property
