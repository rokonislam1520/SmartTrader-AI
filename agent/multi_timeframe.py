"""Multi-timeframe market analysis for SmartTrader-AI."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from agent.market_analyzer import MarketAnalyzer
from agent.signal_generator import SignalGenerator


class MultiTimeframeAnalyzer:
    """Analyze a symbol across 1h, 4h, and 1d timeframes.

    Each timeframe is converted to a BUY/SELL/HOLD signal with the existing
    :class:`SignalGenerator`. The configured weights are applied to the signal
    votes and confidence values, while failed timeframes are isolated so one
    unavailable data source does not prevent the remaining analysis.
    """

    TIMEFRAME_WEIGHTS: Mapping[str, float] = {"1h": 0.30, "4h": 0.40, "1d": 0.30}
    VALID_SIGNALS = frozenset({"BUY", "SELL", "HOLD"})

    def __init__(
        self,
        market_analyzer: Optional[MarketAnalyzer] = None,
        signal_generator: Optional[SignalGenerator] = None,
    ) -> None:
        """Initialize the analyzer, optionally reusing existing components."""
        self.market_analyzer = market_analyzer or MarketAnalyzer()
        self.signal_generator = signal_generator or SignalGenerator()

    def analyze(self, symbol: str) -> Dict[str, Any]:
        """Return weighted multi-timeframe signals for ``symbol``.

        Failed timeframe requests are recorded under ``errors`` and do not
        raise to callers. The combined confidence is reduced when successful
        timeframe decisions disagree with the final weighted decision.
        """
        normalized_symbol = str(symbol).strip().upper()
        if not normalized_symbol:
            raise ValueError("Trading symbol cannot be empty.")

        timeframes: Dict[str, Dict[str, Any]] = {}
        errors: Dict[str, str] = {}
        weighted_votes = {signal: 0.0 for signal in self.VALID_SIGNALS}

        for timeframe, weight in self.TIMEFRAME_WEIGHTS.items():
            try:
                market_analysis = self.market_analyzer.analyze_market(normalized_symbol, timeframe)
                signal = self.signal_generator.generate_signal(market_analysis)
                timeframe_signal = str(signal.get("signal", "HOLD")).upper()
                if timeframe_signal not in self.VALID_SIGNALS:
                    timeframe_signal = "HOLD"
                confidence = self._safe_confidence(signal.get("confidence", 0.0))
                timeframes[timeframe] = {
                    "signal": timeframe_signal,
                    "confidence": round(confidence, 2),
                    "weight": weight,
                    "analysis": market_analysis,
                }
                weighted_votes[timeframe_signal] += weight
            except Exception as exc:
                errors[timeframe] = str(exc)
                print(f"[MultiTimeframeAnalyzer] {normalized_symbol} {timeframe} failed: {exc}")

        if not timeframes:
            return {
                "symbol": normalized_symbol,
                "timeframes": {},
                "combined_signal": "HOLD",
                "confidence": 0.0,
                "agreement": 0,
                "agreement_count": 0,
                "successful_timeframes": 0,
                "errors": errors,
            }

        combined_signal = max(
            self.VALID_SIGNALS,
            key=lambda signal: (weighted_votes[signal], signal == "HOLD"),
        )
        successful_weight = sum(float(item["weight"]) for item in timeframes.values())
        weighted_confidence = sum(
            float(item["confidence"]) * float(item["weight"])
            for item in timeframes.values()
        ) / successful_weight
        agreement_count = sum(
            1 for item in timeframes.values() if item["signal"] == combined_signal
        )
        agreement_ratio = agreement_count / len(timeframes)
        combined_confidence = weighted_confidence * agreement_ratio

        result = {
            "symbol": normalized_symbol,
            "timeframes": timeframes,
            "combined_signal": combined_signal,
            "confidence": round(combined_confidence, 2),
            "agreement": agreement_count,
            "agreement_count": agreement_count,
            "successful_timeframes": len(timeframes),
            "agreement_ratio": round(agreement_ratio, 4),
            "weighted_votes": {key: round(value, 4) for key, value in weighted_votes.items()},
            "errors": errors,
        }
        print(
            f"[MultiTimeframeAnalyzer] {normalized_symbol}: {combined_signal} | "
            f"confidence={combined_confidence:.2f}% | agreement={agreement_count}/{len(timeframes)}"
        )
        return result

    @staticmethod
    def _safe_confidence(value: Any) -> float:
        """Normalize a possibly malformed confidence value to 0..100."""
        try:
            return max(0.0, min(100.0, float(value)))
        except (TypeError, ValueError):
            return 0.0

    analyze_market = analyze


__all__ = ["MultiTimeframeAnalyzer"]
