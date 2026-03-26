"""Report generators for pvValidator validation results.

Supports multiple output formats:
- JSON: Machine-readable, API-friendly
- HTML: Interactive report with color-coded PV segments
- CSV: Backwards-compatible with original pvValidator output
"""

import html as html_mod
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .rules import ValidationResult

logger = logging.getLogger("pvvalidator")


class JSONReporter:
    """Generate JSON validation reports."""

    def generate(
        self,
        results: List[ValidationResult],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        report = {
            "generated": datetime.now().isoformat(),
            "pvvalidator_version": metadata.get("version", "") if metadata else "",
            "rule_document": (
                metadata.get("document", "ESS-0000757") if metadata else "ESS-0000757"
            ),
            "summary": self._summary(results),
            "results": [self._result_to_dict(r) for r in results],
        }
        return json.dumps(report, indent=2, ensure_ascii=False)

    def _summary(self, results: List[ValidationResult]) -> Dict:
        total = len(results)
        valid = sum(1 for r in results if r.format_valid and not r.has_errors)
        errors = sum(1 for r in results if r.has_errors)
        warnings = sum(1 for r in results if r.has_warnings and not r.has_errors)
        invalid_format = sum(1 for r in results if not r.format_valid)
        return {
            "total_pvs": total,
            "valid": valid,
            "errors": errors,
            "warnings": warnings,
            "invalid_format": invalid_format,
        }

    def _result_to_dict(self, result: ValidationResult) -> Dict:
        d = {
            "pv": result.pv,
            "status": result.status,
            "format_valid": result.format_valid,
        }
        if result.components:
            d["components"] = {
                "system": result.components.system,
                "subsystem": result.components.subsystem,
                "discipline": result.components.discipline,
                "device": result.components.device,
                "index": result.components.index,
                "property": result.components.property,
                "format_type": result.components.format_type,
            }
        d["messages"] = [
            {
                "severity": m.severity.value,
                "message": m.message,
                "rule_id": m.rule_id,
            }
            for m in result.messages
        ]
        if result.suggestions:
            d["suggestions"] = [
                {
                    "rule_id": s.rule_id,
                    "suggested": s.suggested,
                    "description": s.description,
                    "applicability": s.applicability.value,
                    "verified": s.verified,
                }
                for s in result.suggestions
                if s.suggested  # only include suggestions with actual content
            ]
        return d


class HTMLReporter:
    """Generate interactive HTML validation reports."""

    # Color mapping for PV segments
    COLORS = {
        "system": "#4C9EEB",
        "subsystem": "#2DD4BF",
        "discipline": "#A78BFA",
        "device": "#FB923C",
        "index": "#FBBF24",
        "property": "#34D399",
    }

    def generate(
        self,
        results: List[ValidationResult],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        summary = self._summary(results)
        rows_html = "\n".join(self._result_row(r) for r in results)
        version = metadata.get("version", "") if metadata else ""
        document = (
            metadata.get("document", "ESS-0000757") if metadata else "ESS-0000757"
        )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>pvValidator Report</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: 'Inter', sans-serif; background: #0A0A0A; color: #EDEDED; padding: 32px; line-height: 1.6; }}
.container {{ max-width: 1200px; margin: 0 auto; }}
h1 {{ font-size: 2rem; font-weight: 700; margin-bottom: 8px; }}
.meta {{ color: #8A8A8A; font-size: 14px; margin-bottom: 32px; }}
.summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px; margin-bottom: 32px; }}
.stat {{ background: #141414; border: 1px solid #2A2A2A; border-radius: 12px; padding: 20px; text-align: center; }}
.stat-value {{ font-size: 2rem; font-weight: 700; }}
.stat-label {{ font-size: 12px; color: #8A8A8A; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 4px; }}
.stat-valid .stat-value {{ color: #34D399; }}
.stat-error .stat-value {{ color: #F87171; }}
.stat-warn .stat-value {{ color: #FBBF24; }}
table {{ width: 100%; border-collapse: separate; border-spacing: 0; }}
th {{ text-align: left; padding: 12px 16px; font-size: 12px; font-weight: 600; text-transform: uppercase;
     letter-spacing: 0.05em; color: #8A8A8A; border-bottom: 2px solid #2A2A2A; position: sticky; top: 0; background: #0A0A0A; }}
td {{ padding: 10px 16px; border-bottom: 1px solid #1E1E1E; font-size: 14px; }}
tr:hover td {{ background: #141414; }}
.pv {{ font-family: 'JetBrains Mono', monospace; font-size: 13px; }}
.seg {{ padding: 2px 6px; border-radius: 4px; font-size: 12px; }}
.seg-sys {{ background: rgba(76,158,235,0.15); color: #4C9EEB; }}
.seg-sub {{ background: rgba(45,212,191,0.15); color: #2DD4BF; }}
.seg-dis {{ background: rgba(167,139,250,0.15); color: #A78BFA; }}
.seg-dev {{ background: rgba(251,146,60,0.15); color: #FB923C; }}
.seg-idx {{ background: rgba(251,191,36,0.15); color: #FBBF24; }}
.seg-prop {{ background: rgba(52,211,153,0.15); color: #34D399; }}
.status-valid {{ color: #34D399; }}
.status-warning {{ color: #FBBF24; }}
.status-error {{ color: #F87171; }}
.messages {{ font-size: 12px; color: #8A8A8A; max-width: 400px; }}
.msg-error {{ color: #F87171; }}
.msg-warning {{ color: #FBBF24; }}
.msg-info {{ color: #8A8A8A; }}
.filter {{ margin-bottom: 16px; }}
.filter input {{ padding: 10px 16px; background: #141414; border: 1px solid #2A2A2A; border-radius: 8px;
               color: #EDEDED; font-size: 14px; width: 300px; font-family: 'JetBrains Mono', monospace; }}
.filter input::placeholder {{ color: #555; }}
@media print {{ body {{ background: #fff; color: #000; }} th {{ background: #fff; }} .filter {{ display: none; }} }}
</style>
</head>
<body>
<div class="container">
  <h1>pvValidator Report</h1>
  <div class="meta">
    {document} | pvValidator {version} | Generated {datetime.now().strftime("%Y-%m-%d %H:%M")}
  </div>
  <div class="summary">
    <div class="stat"><div class="stat-value">{summary['total_pvs']}</div><div class="stat-label">Total PVs</div></div>
    <div class="stat stat-valid"><div class="stat-value">{summary['valid']}</div><div class="stat-label">Valid</div></div>
    <div class="stat stat-error"><div class="stat-value">{summary['errors']}</div><div class="stat-label">Errors</div></div>
    <div class="stat stat-warn"><div class="stat-value">{summary['warnings']}</div><div class="stat-label">Warnings</div></div>
  </div>
  <div class="filter">
    <input type="text" id="search" placeholder="Filter PVs..." oninput="filterTable(this.value)">
  </div>
  <table id="results">
    <thead><tr><th>PV Name</th><th>Components</th><th>Status</th><th>Messages</th></tr></thead>
    <tbody>
{rows_html}
    </tbody>
  </table>
</div>
<script>
function filterTable(q) {{
  var rows = document.querySelectorAll('#results tbody tr');
  q = q.toLowerCase();
  rows.forEach(function(r) {{ r.style.display = r.textContent.toLowerCase().includes(q) ? '' : 'none'; }});
}}
</script>
</body>
</html>"""

    def _summary(self, results):
        total = len(results)
        valid = sum(1 for r in results if r.format_valid and not r.has_errors)
        errors = sum(1 for r in results if r.has_errors)
        warnings = sum(1 for r in results if r.has_warnings and not r.has_errors)
        return {
            "total_pvs": total,
            "valid": valid,
            "errors": errors,
            "warnings": warnings,
        }

    def _result_row(self, result: ValidationResult) -> str:
        # PV name
        pv_html = f'<span class="pv">{self._escape(result.pv)}</span>'

        # Components
        if result.components:
            c = result.components
            parts = []
            if c.system:
                parts.append(
                    f'<span class="seg seg-sys">{self._escape(c.system)}</span>'
                )
            if c.subsystem:
                parts.append(
                    f'<span class="seg seg-sub">{self._escape(c.subsystem)}</span>'
                )
            if c.discipline:
                parts.append(
                    f'<span class="seg seg-dis">{self._escape(c.discipline)}</span>'
                )
            if c.device:
                parts.append(
                    f'<span class="seg seg-dev">{self._escape(c.device)}</span>'
                )
            if c.index:
                parts.append(
                    f'<span class="seg seg-idx">{self._escape(c.index)}</span>'
                )
            if c.property:
                parts.append(
                    f'<span class="seg seg-prop">{self._escape(c.property)}</span>'
                )
            comp_html = " ".join(parts)
        else:
            comp_html = '<span style="color:#555">—</span>'

        # Status
        status = result.status
        if "NOT VALID" in status:
            status_class = "status-error"
        elif "Warning" in status:
            status_class = "status-warning"
        else:
            status_class = "status-valid"
        status_html = f'<span class="{status_class}">{self._escape(status)}</span>'

        # Messages
        msg_parts = []
        for m in result.messages:
            cls = f"msg-{m.severity.value.lower()}"
            msg_parts.append(f'<div class="{cls}">{self._escape(str(m))}</div>')
        msg_html = (
            f'<div class="messages">{"".join(msg_parts)}</div>' if msg_parts else ""
        )

        return f"    <tr><td>{pv_html}</td><td>{comp_html}</td><td>{status_html}</td><td>{msg_html}</td></tr>"

    @staticmethod
    def _escape(s: str) -> str:
        return html_mod.escape(s, quote=True)
