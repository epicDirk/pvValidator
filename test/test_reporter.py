"""Tests for the report generators."""

import json

import pytest

from pvValidatorUtils.parser import parse_pv
from pvValidatorUtils.reporter import HTMLReporter, JSONReporter
from pvValidatorUtils.rules import Severity, ValidationMessage, ValidationResult


@pytest.fixture
def sample_results():
    """Sample validation results for testing."""
    valid_pv = parse_pv("DTL-010:EMR-TT-001:Temperature")
    invalid_pv = parse_pv("DTL-010:EMR-TT-001:Temperature-S")
    return [
        ValidationResult(
            pv="DTL-010:EMR-TT-001:Temperature",
            format_valid=True,
            components=valid_pv,
            messages=[],
        ),
        ValidationResult(
            pv="DTL-010:EMR-TT-001:Temperature-S",
            format_valid=True,
            components=invalid_pv,
            messages=[
                ValidationMessage(
                    Severity.ERROR, "Setpoint suffix must be -SP", "PROP-SP"
                ),
            ],
        ),
        ValidationResult(
            pv="INVALID::FORMAT::HERE",
            format_valid=False,
            messages=[
                ValidationMessage(Severity.ERROR, "Invalid PV format"),
            ],
        ),
    ]


@pytest.fixture
def metadata():
    return {"version": "1.8.0", "document": "ESS-0000757"}


class TestJSONReporter:

    def test_generates_valid_json(self, sample_results, metadata):
        reporter = JSONReporter()
        output = reporter.generate(sample_results, metadata)
        data = json.loads(output)
        assert "summary" in data
        assert "results" in data

    def test_summary_counts(self, sample_results, metadata):
        reporter = JSONReporter()
        data = json.loads(reporter.generate(sample_results, metadata))
        assert data["summary"]["total_pvs"] == 3
        assert data["summary"]["valid"] == 1
        assert data["summary"]["errors"] == 2

    def test_result_structure(self, sample_results, metadata):
        reporter = JSONReporter()
        data = json.loads(reporter.generate(sample_results, metadata))
        first = data["results"][0]
        assert first["pv"] == "DTL-010:EMR-TT-001:Temperature"
        assert first["format_valid"] is True
        assert "components" in first
        assert first["components"]["system"] == "DTL"

    def test_error_messages_in_output(self, sample_results, metadata):
        reporter = JSONReporter()
        data = json.loads(reporter.generate(sample_results, metadata))
        second = data["results"][1]
        assert len(second["messages"]) == 1
        assert second["messages"][0]["rule_id"] == "PROP-SP"

    def test_metadata_in_output(self, sample_results, metadata):
        reporter = JSONReporter()
        data = json.loads(reporter.generate(sample_results, metadata))
        assert data["pvvalidator_version"] == "1.8.0"
        assert data["rule_document"] == "ESS-0000757"


class TestHTMLReporter:

    def test_generates_html(self, sample_results, metadata):
        reporter = HTMLReporter()
        output = reporter.generate(sample_results, metadata)
        assert "<!DOCTYPE html>" in output
        assert "pvValidator Report" in output

    def test_contains_pv_names(self, sample_results, metadata):
        reporter = HTMLReporter()
        output = reporter.generate(sample_results, metadata)
        assert "DTL-010:EMR-TT-001:Temperature" in output

    def test_contains_color_coded_segments(self, sample_results, metadata):
        reporter = HTMLReporter()
        output = reporter.generate(sample_results, metadata)
        assert "seg-sys" in output
        assert "seg-prop" in output

    def test_contains_summary_stats(self, sample_results, metadata):
        reporter = HTMLReporter()
        output = reporter.generate(sample_results, metadata)
        assert "Total PVs" in output
        assert "Valid" in output

    def test_contains_filter_input(self, sample_results, metadata):
        reporter = HTMLReporter()
        output = reporter.generate(sample_results, metadata)
        assert "filterTable" in output
        assert 'id="search"' in output

    def test_error_messages_visible(self, sample_results, metadata):
        reporter = HTMLReporter()
        output = reporter.generate(sample_results, metadata)
        assert "Setpoint suffix must be -SP" in output
        assert "msg-error" in output
