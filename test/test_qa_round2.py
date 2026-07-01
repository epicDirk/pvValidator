"""Regression tests for the QA round-2 findings (2026-07-01).

Pure-Python (no SWIG/curses): parser, rules and naming_client only. Covers the
new findings verified in this round; the classic-pipeline P0/exit-code behaviour
is exercised by the SWIG-dependent test_validator.py in the e3/Docker image.
"""

import requests

from pvValidatorUtils.exceptions import NamingServiceConnectionError
from pvValidatorUtils.naming_client import NamingServiceClient
from pvValidatorUtils.parser import parse_pv
from pvValidatorUtils.reporter import JSONReporter
from pvValidatorUtils.rules import (
    Severity,
    ValidationMessage,
    ValidationResult,
    check_all_rules,
    check_property_length,
    normalize_for_confusion,
)


def _rule_ids(pv):
    c = parse_pv(pv)
    assert c is not None, f"{pv} should parse"
    return [m.rule_id for m in check_all_rules(c)]


# --------------------------------------------------------------------------- N1
def test_trailing_dash_empty_index_rejected():
    # trailing dash -> empty index must be rejected, like the 2-segment form
    assert parse_pv("DTL-010:EMR-TT-:Temperature") is None
    assert parse_pv("DTL-010:EMR-TT:Temperature") is None


# --------------------------------------------------------------------------- N2
def test_whitespace_and_unicode_property_is_error():
    for pv in (
        "DTL-010:EMR-TT-001:Foo Bar",  # space
        "DTL-010:EMR-TT-001:Foo\tBar",  # tab
        "DTL-010:EMR-TT-001:Temp°C",  # ° (non-ASCII)
        "DTL-010:EMR-TT-001:Nébu",  # é (non-ASCII letter)
    ):
        assert "PROP-11-CHAR" in _rule_ids(pv), pv
    # a clean ASCII property is still fine
    assert "PROP-11-CHAR" not in _rule_ids("DTL-010:EMR-TT-001:Temperature")


# --------------------------------------------------------------------------- N3
def test_known_short_with_suffix_no_prop3():
    for prop in ("On-SP", "Set-SP", "Low-SP", "On-RB"):
        c = parse_pv(f"DTL-010:EMR-TT-001:{prop}")
        assert "PROP-3" not in [m.rule_id for m in check_property_length(c)], prop
    # a genuinely-short *unknown* property still warns
    c = parse_pv("DTL-010:EMR-TT-001:Abc-SP")
    assert "PROP-3" in [m.rule_id for m in check_property_length(c)]


# --------------------------------------------------------------------------- F8
def test_long_numeric_index_warns_not_silent():
    assert "IDX-LONG" in _rule_ids("DTL-010:EMR-TT-12345:Temp")
    assert "IDX-LONG" in _rule_ids("DTL-010:EMR-TT-123456:Temp")
    assert _rule_ids("DTL-010:EMR-TT-001:Temp") == []  # canonical: silent
    # Cryo/Vac 5-digit is LEGACY-5DIGIT, not a duplicate IDX-LONG
    cryo = _rule_ids("DTL-010:Cryo-TT-12345:Temp")
    assert "LEGACY-5DIGIT" in cryo and "IDX-LONG" not in cryo


# --------------------------------------------------------------------------- F7
def test_leading_zero_confusion_documented_behaviour():
    # documented decision (pending Alfio): Temp01 and Temp1 are DISTINCT skeletons
    assert normalize_for_confusion("Temp01") != normalize_for_confusion("Temp1")


# --------------------------------------------------------------------------- N9
def test_reporter_summary_buckets_partition_total():
    warn = ValidationResult(
        pv="X:A-B-001:foo",
        format_valid=True,
        messages=[ValidationMessage(Severity.WARNING, "w", "PROP-11-CASE")],
    )
    clean = ValidationResult(pv="X:A-B-001:Temp", format_valid=True)
    s = JSONReporter()._summary([warn, clean])
    assert s["valid"] == 1  # only the strictly-clean PV, not the warnings-only one
    assert s["warnings"] == 1
    assert (
        s["valid"] + s["warnings"] + s["errors"] + s["invalid_format"] == s["total_pvs"]
    )


# ------------------------------------------------------- CLI exit / conflicts (self-review)
def _run_cli(argv, tmp_path, lines):
    import sys

    from pvValidatorUtils.pvValidator import main

    f = tmp_path / "pvs.txt"
    f.write_text("\n".join(lines) + "\n")
    old = sys.argv
    sys.argv = ["pvValidator", "-i", str(f)] + argv
    try:
        main()
        return 0
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    finally:
        sys.argv = old


def test_suggest_exit_1_on_duplicate_property(tmp_path):
    # Two format-valid PVs with a duplicate property on the same device -> PROP-1
    # ERROR. --suggest must exit 1 (matching --format json), not 0. Lowercase 'temp'
    # yields a fix suggestion so no valid-check-mark is printed.
    code = _run_cli(
        ["--noapi", "--suggest"],
        tmp_path,
        ["DTL-010:EMR-TT-001:temp", "DTL-010:EMR-TT-001:temp"],
    )
    assert code == 1


def test_suggest_plus_stdout_rejected(tmp_path):
    # --suggest + --stdout is a competing-output conflict -> argparse error (exit 2).
    code = _run_cli(["--suggest", "--stdout"], tmp_path, ["DTL-010:EMR-TT-001:temp"])
    assert code == 2


# ---------------------------------------------------------------- naming_client
class _FakeResp:
    def __init__(self, status=200, json_data=None, raise_json=False):
        self.status_code = status
        self._json = json_data
        self._raise_json = raise_json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(str(self.status_code))

    def json(self):
        if self._raise_json:
            raise ValueError("no json")
        return self._json


def test_check_connectivity_http_500_is_unreachable():  # F5
    c = NamingServiceClient()
    c.session.head = lambda url, timeout=None: _FakeResp(500)
    try:
        c.check_connectivity()
        assert False, "HTTP 500 should raise NamingServiceConnectionError"
    except NamingServiceConnectionError:
        pass


def test_check_connectivity_uses_configured_timeout():  # N7
    c = NamingServiceClient(timeout=9)
    seen = {}
    c.session.head = lambda url, timeout=None: (
        seen.update(t=timeout) or _FakeResp(200)
    )
    c.check_connectivity()
    assert seen["t"] == 9


def test_validate_system_bad_shape_no_crash():  # F12
    c = NamingServiceClient()
    c.session.get = lambda url, timeout=None: _FakeResp(200, {"unexpected": "dict"})
    assert c.validate_system("DTL") is False  # not an AttributeError


def test_transient_failure_not_cached():  # N6
    c = NamingServiceClient()
    state = {"n": 0}

    def flaky(url, timeout=None):
        state["n"] += 1
        if state["n"] == 1:
            raise requests.exceptions.ConnectionError("boom")
        return _FakeResp(
            200, [{"status": "Approved", "type": "System Structure", "level": "1"}]
        )

    c.session.get = flaky
    assert c.validate_system("DTL") is False  # transient -> False, NOT cached
    assert c.validate_system("DTL") is True  # retry succeeds


def test_search_parts_malformed_and_bad_shape():  # N8 + F12
    c = NamingServiceClient()
    c.session.get = lambda url, timeout=None: _FakeResp(200, raise_json=True)
    assert c.search_parts("DT") == []
    c.session.get = lambda url, timeout=None: _FakeResp(200, {"a": 1})
    assert c.search_parts("DT") == []
