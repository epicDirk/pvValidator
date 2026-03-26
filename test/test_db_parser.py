"""Tests for EPICS DB file parser regex (pvUtils._checkEPICSDBFile).

These tests verify the fix from fragile r.split(',') to regex-based
record parsing. Previously:
- PVs starting with 'f' or 'i' were silently dropped
- Commas in field values broke the split
"""

import re

import pytest

# Test the regex directly (same pattern used in pvUtils)
RECORD_PATTERN = re.compile(r'record\s*\(\s*\w+\s*,\s*"([^"]+)"\s*\)')


class TestRecordRegex:
    """Test the record() regex pattern used for DB parsing."""

    def test_standard_record(self):
        line = 'record(ai, "DTL-010:EMR-TT-001:Temperature")'
        m = RECORD_PATTERN.search(line)
        assert m is not None
        assert m.group(1) == "DTL-010:EMR-TT-001:Temperature"

    def test_record_with_extra_spaces(self):
        line = 'record(  ao  ,  "DTL-010:EMR-TT-001:SetPoint-SP"  )'
        m = RECORD_PATTERN.search(line)
        assert m is not None
        assert m.group(1) == "DTL-010:EMR-TT-001:SetPoint-SP"

    def test_pv_starting_with_f(self):
        """Previously dropped by startswith('f') filter."""
        line = 'record(ai, "ISrc:Vac-VG-001:filamentCurrent")'
        m = RECORD_PATTERN.search(line)
        assert m is not None
        assert m.group(1) == "ISrc:Vac-VG-001:filamentCurrent"

    def test_pv_starting_with_i(self):
        """Previously dropped by startswith('i') filter."""
        line = 'record(ai, "ISrc:Vac-VG-001:ionGaugePressure")'
        m = RECORD_PATTERN.search(line)
        assert m is not None
        assert m.group(1) == "ISrc:Vac-VG-001:ionGaugePressure"

    def test_fanout_record_type(self):
        """Record type 'fanout' starts with 'f' — was previously filtered."""
        line = 'record(fanout, "DTL-010:EMR-FO-001:FanSeq")'
        m = RECORD_PATTERN.search(line)
        assert m is not None
        assert m.group(1) == "DTL-010:EMR-FO-001:FanSeq"

    def test_int64in_record_type(self):
        """Record type 'int64in' starts with 'i' — was previously filtered."""
        line = 'record(int64in, "DTL-010:EMR-II-001:IntValue")'
        m = RECORD_PATTERN.search(line)
        assert m is not None
        assert m.group(1) == "DTL-010:EMR-II-001:IntValue"

    def test_record_with_comma_in_subsequent_field(self):
        """Line with record() followed by field with comma — regex extracts PV correctly."""
        line = 'record(calcout, "DTL-010:EMR-Calc-001:ConvertedValue") {'
        m = RECORD_PATTERN.search(line)
        assert m is not None
        assert m.group(1) == "DTL-010:EMR-Calc-001:ConvertedValue"

    def test_field_line_not_matched(self):
        """Field lines should NOT match the record pattern."""
        line = '    field(CALC, "A>B?1,0")'
        m = RECORD_PATTERN.search(line)
        assert m is None

    def test_comment_line_not_matched(self):
        """Comment lines are pre-filtered, but regex also shouldn't match garbage."""
        line = '# record(ai, "SHOULD-NOT:APPEAR:InResults")'
        # This would match the regex, but comments are filtered before regex
        # Just verify the regex works on the content part
        m = RECORD_PATTERN.search(line)
        # It CAN match inside comments — the caller filters comments first
        assert m is not None  # regex matches, but caller skips comment lines

    def test_no_record_on_line(self):
        line = '    field(DESC, "Some description")'
        m = RECORD_PATTERN.search(line)
        assert m is None

    def test_empty_pv_name(self):
        """Empty PV name in record() — regex requires at least 1 char, so no match."""
        line = 'record(ai, "")'
        m = RECORD_PATTERN.search(line)
        assert m is None  # [^"]+ requires at least one character

    def test_pv_with_macros(self):
        """PVs with EPICS macros like $(P)$(R) should be extracted as-is."""
        line = 'record(ai, "$(P)$(R)Temperature")'
        m = RECORD_PATTERN.search(line)
        assert m is not None
        assert m.group(1) == "$(P)$(R)Temperature"

    def test_multiline_record_opening(self):
        """Only the line with record() matters, body lines are ignored."""
        lines = [
            'record(ai, "DTL-010:EMR-TT-001:Temperature") {',
            '    field(DESC, "Temperature sensor")',
            "}",
        ]
        results = []
        for line in lines:
            m = RECORD_PATTERN.search(line)
            if m:
                results.append(m.group(1))
        assert results == ["DTL-010:EMR-TT-001:Temperature"]


class TestDBFileIntegration:
    """Integration tests using the actual test fixture DB file."""

    @pytest.fixture
    def db_records(self):
        """Parse the test DB fixture file using the same logic as pvUtils."""
        import pathlib

        db_path = pathlib.Path(__file__).parent / "fixtures" / "test_records.db"
        results = []
        with open(db_path) as f:
            for line in f:
                if line.lstrip().startswith("#"):
                    continue
                m = RECORD_PATTERN.search(line)
                if m:
                    results.append(m.group(1))
        return results

    def test_all_records_found(self, db_records):
        """Should find all 7 records (including fanout and int64in)."""
        assert len(db_records) == 7

    def test_standard_records_present(self, db_records):
        assert "DTL-010:EMR-TT-001:Temperature" in db_records
        assert "DTL-010:EMR-TT-001:SetPoint-SP" in db_records

    def test_pv_starting_with_f_included(self, db_records):
        """filamentCurrent was dropped by the old parser."""
        assert "ISrc:Vac-VG-001:filamentCurrent" in db_records

    def test_pv_starting_with_i_included(self, db_records):
        """ionGaugePressure was dropped by the old parser."""
        assert "ISrc:Vac-VG-001:ionGaugePressure" in db_records

    def test_fanout_record_included(self, db_records):
        """fanout record type was dropped by the old parser."""
        assert "DTL-010:EMR-FO-001:FanSeq" in db_records

    def test_int64in_record_included(self, db_records):
        """int64in record type was dropped by the old parser."""
        assert "DTL-010:EMR-II-001:IntValue" in db_records

    def test_commented_record_excluded(self, db_records):
        """Commented-out records should not appear."""
        assert "SHOULD-NOT:APPEAR:InResults" not in db_records

    def test_comma_in_field_no_impact(self, db_records):
        """The calcout record with comma in CALC field should parse correctly."""
        assert "DTL-010:EMR-Calc-001:ConvertedValue" in db_records
