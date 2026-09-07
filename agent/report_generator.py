"""Human-readable and machine-readable trading analysis reports."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping


class ReportGenerator:
    """Generate, format, and persist comprehensive trading analysis reports.

    Reports intentionally accept loosely structured analysis dictionaries because
    analyzers may add fields over time. Missing sections are represented safely
    rather than causing the reporting path to interrupt trading.
    """

    def __init__(self, reports_dir: str | Path | None = None) -> None:
        """Initialize the generator and choose a safe reports directory."""
        project_root = Path(__file__).resolve().parent.parent
        self.reports_dir = Path(reports_dir) if reports_dir else project_root / "reports"

    @staticmethod
    def _section(data: Mapping[str, Any], name: str) -> Mapping[str, Any]:
        value = data.get(name, {})
        return value if isinstance(value, Mapping) else {"value": value}

    @staticmethod
    def _lines(value: Any, prefix: str = "  ") -> list[str]:
        if isinstance(value, Mapping):
            return [f"{prefix}{key}: {item}" for key, item in value.items()]
        if isinstance(value, (list, tuple)):
            return [f"{prefix}- {item}" for item in value]
        return [f"{prefix}{value}"]

    def generate_text_report(self, analysis_data: Mapping[str, Any]) -> str:
        """Return a comprehensive text report for one cycle or dashboard snapshot."""
        data = dict(analysis_data)
        sections = (
            ("SENTIMENT", "sentiment"),
            ("MULTI-TIMEFRAME ANALYSIS", "multi_timeframe"),
            ("TECHNICAL ANALYSIS", "technical"),
            ("SIGNAL", "signal"),
            ("RISK", "risk"),
            ("PORTFOLIO", "portfolio"),
        )
        output = [
            "SMARTTRADER-AI ANALYSIS REPORT",
            f"Generated: {data.get('generated_at', datetime.now(timezone.utc).isoformat(timespec='seconds'))}",
            f"Symbol(s): {data.get('symbols', data.get('symbol', 'N/A'))}",
            "=" * 72,
        ]
        for title, key in sections:
            output.extend(["", title, "-" * len(title)])
            section = self._section(data, key)
            if not section:
                output.append("  No data available.")
            else:
                for field, value in section.items():
                    if isinstance(value, (Mapping, list, tuple)):
                        output.append(f"  {field}:")
                        output.extend(self._lines(value, "    "))
                    else:
                        output.append(f"  {field}: {value}")
        return "\n".join(output) + "\n"

    def generate_json_report(self, analysis_data: Mapping[str, Any]) -> Dict[str, Any]:
        """Return a JSON-serializable report with all standard sections."""
        report: Dict[str, Any] = dict(analysis_data)
        report.setdefault("generated_at", datetime.now(timezone.utc).isoformat(timespec="seconds"))
        for key in ("sentiment", "multi_timeframe", "technical", "signal", "risk", "portfolio"):
            report.setdefault(key, {})
        return report

    def save_report(self, report_text: str, filename: str) -> Path:
        """Safely save text under the reports directory and return its path."""
        safe_name = Path(filename).name
        if not safe_name or safe_name in {".", ".."}:
            raise ValueError("filename must contain a valid file name")
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        destination = (self.reports_dir / safe_name).resolve()
        if self.reports_dir.resolve() not in destination.parents:
            raise ValueError("filename must remain inside the reports directory")
        destination.write_text(report_text, encoding="utf-8")
        return destination


__all__ = ["ReportGenerator"]
