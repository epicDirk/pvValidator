"""Regression tests: the HTML report must escape user-controlled PV data.

The reporter already escapes every PV-derived value via html.escape(); these
tests lock that in so a malicious PV name can never inject markup/script when
the generated report is opened in a browser.
"""

from pvValidatorUtils.reporter import HTMLReporter
from pvValidatorUtils.rules import Severity, ValidationMessage, ValidationResult

META = {"version": "2.0.0", "document": "ESS-0000757"}


def _html_for(pv, messages=None):
    result = ValidationResult(pv=pv, format_valid=False, messages=messages or [])
    return HTMLReporter().generate([result], META)


def test_script_in_pv_name_is_escaped():
    html = _html_for("DTL<script>alert(1)</script>:X:Y")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_img_onerror_in_message_is_escaped():
    html = _html_for(
        "DTL-010:EMR-TT-001:Temp",
        messages=[ValidationMessage(Severity.ERROR, '"><img src=x onerror=alert(1)>')],
    )
    assert "<img src=x" not in html
    assert "&lt;img" in html
