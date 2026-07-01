"""Regression tests for QA round 3 (adversarial bug-hunt fixes).

Pure-Python only — no SWIG/curses — so they run in the GitHub CI pure-Python job.
The classic-pipeline (SWIG) counterparts for E and the naming-unreachable exit live
in test_validator.py (marker: swig).

Fix key (see CHANGELOG round 3):
  A  internal-PV '#' no longer counted toward property length
  B  leading-zero normalisation only collapses LEADING zeros of a digit group
  C  naming_client mnemonicPath match is segment-boundary-anchored
  D  high-level '::' PROP-1 reaches the JSON/HTML report and the exit code
  reporter summary buckets partition the total
  rule_loader empty/comment-only YAML falls back to built-in defaults
  autofix SP_ legacy prefix is MANUAL (ambiguous setpoint semantics)
"""

import os
import sys
import tempfile

from pvValidatorUtils.autofix import Applicability, suggest_fixes
from pvValidatorUtils.naming_client import _mnemonic_path_matches
from pvValidatorUtils.parser import parse_pv
from pvValidatorUtils.reporter import HTMLReporter, JSONReporter
from pvValidatorUtils.rule_loader import RuleConfig
from pvValidatorUtils.rules import (
    Severity,
    ValidationMessage,
    ValidationResult,
    check_all_rules,
    effective_property_length,
    normalize_for_confusion,
)


# --------------------------------------------------------------------------- A
class TestInternalPropertyLength:
    def test_hash_not_counted(self):
        assert effective_property_length("#" + "A" * 25) == 25
        assert effective_property_length("#" + "A" * 26) == 26
        assert effective_property_length("#On-SP") == 2  # '#' and '-SP' both excluded

    def test_internal_25_body_is_not_an_error(self):
        # body is exactly the 25-char SHALL limit -> at most a PROP-2-WARN, no error
        comps = parse_pv("SEE-010:EMR-TT-001:#" + "A" * 25)
        rule_ids = [(m.severity, m.rule_id) for m in check_all_rules(comps)]
        assert (Severity.ERROR, "PROP-2") not in rule_ids

    def test_internal_26_body_is_an_error(self):
        comps = parse_pv("SEE-010:EMR-TT-001:#" + "A" * 26)
        assert any(
            m.rule_id == "PROP-2" and m.severity == Severity.ERROR
            for m in check_all_rules(comps)
        )


# --------------------------------------------------------------------------- B
class TestLeadingZeroNormalisation:
    def test_trailing_zero_runs_do_not_collide(self):
        assert normalize_for_confusion("Val100") != normalize_for_confusion("Val1000")
        assert normalize_for_confusion("Amp30") != normalize_for_confusion("Amp300")

    def test_leading_zero_padding_still_collides(self):
        assert normalize_for_confusion("Ch001") == normalize_for_confusion("Ch0001")

    def test_leading_zero_vs_none_still_distinct(self):
        # F7 documented behaviour (pending Alfio) — unchanged by the fix
        assert normalize_for_confusion("Temp01") != normalize_for_confusion("Temp1")

    def test_idempotent(self):
        for s in ("Ch0001", "Val1000", "Temp01", "A0B0"):
            assert normalize_for_confusion(normalize_for_confusion(s)) == (
                normalize_for_confusion(s)
            )


# --------------------------------------------------------------------------- C
class TestMnemonicPathMatch:
    def test_positive(self):
        assert _mnemonic_path_matches("Acc-DTL-010", "DTL-010")  # subsystem leaf
        assert _mnemonic_path_matches("EMR-TT", "EMR-TT")  # device (exact)

    def test_rejects_substring_false_positives(self):
        assert not _mnemonic_path_matches("Acc-DTL-010", "TL-010")  # wrong system
        assert not _mnemonic_path_matches("Acc-DTL-010", "DTL-01")  # partial leaf
        assert not _mnemonic_path_matches("XEMR-TT", "EMR-TT")  # wrong discipline


# --------------------------------------------------------------------------- D
def _run_main(argv):
    from pvValidatorUtils.pvValidator import main

    old = sys.argv
    sys.argv = ["pvValidator"] + argv
    try:
        main()
        return 0
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    finally:
        sys.argv = old


class TestHighLevelUniquenessInReporter:
    def test_duplicate_high_level_prop1_exits_and_is_reported(self, tmp_path, capsys):
        f = tmp_path / "hl.txt"
        f.write_text("LEBT::Temperature\nLEBT::Temperature\n")
        code = _run_main(["-i", str(f), "--noapi", "--format", "json"])
        out = capsys.readouterr().out
        assert code == 1  # PROP-1 must be exit-effective in the reporter path
        assert "PROP-1" in out

    def test_mixed_invalid_format_does_not_crash(self, tmp_path, capsys):
        f = tmp_path / "mix.txt"
        f.write_text("LEBT::Temperature\nLEBT::Temperature\n@@@garbage\n")
        code = _run_main(["-i", str(f), "--noapi", "--format", "json"])
        capsys.readouterr()
        assert code == 1  # no AttributeError on components=None

    def test_single_high_level_is_clean(self, tmp_path, capsys):
        f = tmp_path / "one.txt"
        f.write_text("LEBT::Temperature\n")
        code = _run_main(["-i", str(f), "--noapi", "--format", "json"])
        capsys.readouterr()
        assert code == 0


# ------------------------------------------------------------------- reporter
class TestReporterSummaryPartition:
    def _sample(self):
        return [
            ValidationResult(pv="OK", format_valid=True, messages=[]),
            ValidationResult(
                pv="ERR",
                format_valid=True,
                messages=[ValidationMessage(Severity.ERROR, "x", "PROP-2")],
            ),
            ValidationResult(
                pv="WARN",
                format_valid=True,
                messages=[ValidationMessage(Severity.WARNING, "w", "PROP-2-WARN")],
            ),
            ValidationResult(
                pv="BAD::FMT",
                format_valid=False,
                messages=[ValidationMessage(Severity.ERROR, "bad", "FMT")],
            ),
        ]

    def test_json_partitions(self):
        s = JSONReporter()._summary(self._sample())
        assert s["valid"] + s["errors"] + s["warnings"] + s["invalid_format"] == (
            s["total_pvs"]
        )

    def test_html_partitions(self):
        s = HTMLReporter()._summary(self._sample())
        assert s["valid"] + s["errors"] + s["warnings"] + s["invalid_format"] == (
            s["total_pvs"]
        )

    def test_html_metadata_escaped(self):
        html = HTMLReporter().generate(
            self._sample(), {"version": "<script>x</script>", "document": "D&D"}
        )
        assert "<script>x</script>" not in html
        assert "&lt;script&gt;" in html


# ----------------------------------------------------------------- rule_loader
class TestRuleLoaderRobustness:
    def test_empty_yaml_falls_back(self):
        fd, path = tempfile.mkstemp(suffix=".yaml")
        os.write(fd, b"# only a comment\n\n")
        os.close(fd)
        try:
            cfg = RuleConfig(path)
            assert cfg.max_property_length == 25  # built-in default, no AttributeError
        finally:
            os.remove(path)

    def test_explain_resolves_fmt_rules(self):
        assert RuleConfig().get_rule("FMT-1") is not None

    def test_recommended_length_from_config(self):
        assert RuleConfig().max_property_length_recommended == 20


# --------------------------------------------------------------------- autofix
class TestAutofixLegacyPrefix:
    def test_sp_prefix_is_manual(self):
        sugg = [s for s in suggest_fixes("SEE-010:EMR-TT-001:SP_Flow")]
        legacy = [s for s in sugg if s.rule_id == "LEGACY-PREFIX"]
        assert legacy, "SP_ should still produce a LEGACY-PREFIX suggestion"
        assert legacy[0].applicability == Applicability.MANUAL
        assert not legacy[0].auto_fixable  # not silently auto-applied

    def test_other_legacy_prefix_still_safe(self):
        sugg = [s for s in suggest_fixes("SEE-010:EMR-TT-001:Cmd_Open")]
        legacy = [s for s in sugg if s.rule_id == "LEGACY-PREFIX"]
        assert legacy and legacy[0].applicability == Applicability.SAFE
