"""Multi-indicator BUY/SELL/HOLD signal generation for SmartTrader-AI."""

from typing import Any, Dict, List, Mapping, Tuple

import numpy as np


class SignalGenerator:
    """Combine technical indicators into a transparent, weighted signal."""

    # The weights sum to 1.0, so the composite score stays in [-1.0, 1.0].
    INDICATOR_WEIGHTS = {
        "rsi": 0.25,
        "macd": 0.25,
        "bollinger": 0.20,
        "volume": 0.15,
        "trend": 0.15,
    }

    def generate_signal(self, market_analysis: Mapping[str, Any]) -> Dict[str, Any]:
        """Generate a signal from a MarketAnalyzer result dictionary.

        Indicator scores are normalized to a common scale before weighting.
        Volume is a confirmation signal, therefore it contributes only +/-0.5.
        Missing optional statuses are treated as neutral rather than causing an
        unsafe directional decision.

        Args:
            market_analysis: Mapping containing the analyzer's indicator values.

        Returns:
            A serializable signal, confidence score, component scores, and reasons.

        Raises:
            ValueError: If the input is not mapping-like or RSI is invalid.
        """
        if not isinstance(market_analysis, Mapping):
            raise ValueError("market_analysis must be a dictionary-like object.")

        try:
            rsi = float(market_analysis["rsi_value"])
            rsi_status = str(market_analysis.get("rsi_status", "")).lower()
            macd_status = str(market_analysis.get("macd_signal", "")).lower()
            bb_status = str(market_analysis.get("bollinger_position", "")).lower()
            volume_status = str(market_analysis.get("volume_status", "")).lower()
            trend_status = str(market_analysis.get("trend_direction", "")).lower()
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid market analysis: {exc}") from exc

        if not np.isfinite(rsi) or not 0 <= rsi <= 100:
            raise ValueError("rsi_value must be a finite number between 0 and 100.")

        scores: Dict[str, float] = {}
        reasons: List[str] = []

        # RSI: classify in the exact requested zones, including boundary values.
        if rsi < 30:
            scores["rsi"] = 1.0
            reasons.append(f"RSI is {rsi:.2f}: strongly oversold (strong buy signal).")
        elif rsi < 40:
            scores["rsi"] = 0.5
            reasons.append(f"RSI is {rsi:.2f}: moderately oversold (buy bias).")
        elif rsi <= 60:
            scores["rsi"] = 0.0
            reasons.append(f"RSI is {rsi:.2f}: neutral momentum.")
        elif rsi <= 70:
            scores["rsi"] = -0.5
            reasons.append(f"RSI is {rsi:.2f}: moderately overbought (sell bias).")
        else:
            scores["rsi"] = -1.0
            reasons.append(f"RSI is {rsi:.2f}: strongly overbought (strong sell signal).")

        # MACD compares the MACD line against its signal line.
        if macd_status == "bullish":
            scores["macd"] = 1.0
            reasons.append("MACD is bullish and supports a buy bias.")
        elif macd_status == "bearish":
            scores["macd"] = -1.0
            reasons.append("MACD is bearish and supports a sell bias.")
        else:
            scores["macd"] = 0.0
            reasons.append("MACD is neutral.")

        # Price position within Bollinger Bands provides mean-reversion context.
        if bb_status == "lower":
            scores["bollinger"] = 1.0
            reasons.append("Price is at the lower Bollinger Band (buy opportunity).")
        elif bb_status == "upper":
            scores["bollinger"] = -1.0
            reasons.append("Price is at the upper Bollinger Band (sell pressure).")
        else:
            scores["bollinger"] = 0.0
            reasons.append("Price is near the Bollinger middle band.")

        # Volume confirms the direction of an existing trend; it never creates
        # a directional signal by itself.
        if volume_status == "above_average" and trend_status == "up":
            scores["volume"] = 0.5
            reasons.append("Above-average volume confirms the uptrend.")
        elif volume_status == "above_average" and trend_status == "down":
            scores["volume"] = -0.5
            reasons.append("Above-average volume confirms the downtrend.")
        else:
            scores["volume"] = 0.0
            reasons.append("Volume does not provide additional confirmation.")

        # Trend uses the SMA ordering supplied by MarketAnalyzer.
        if trend_status == "up":
            scores["trend"] = 1.0
            reasons.append("SMA structure indicates a strong uptrend.")
        elif trend_status == "down":
            scores["trend"] = -1.0
            reasons.append("SMA structure indicates a strong downtrend.")
        else:
            scores["trend"] = 0.0
            reasons.append("SMA structure is mixed and indicates sideways conditions.")

        composite = float(
            np.clip(
                sum(scores[name] * self.INDICATOR_WEIGHTS[name] for name in scores),
                -1.0,
                1.0,
            )
        )
        confidence = self._calculate_confidence(scores, composite)
        strength = "STRONG" if confidence >= 80 else "MODERATE" if confidence >= 60 else "WEAK"
        if composite > 0.3 and confidence >= 70:
            final_signal = "BUY"
        elif composite < -0.3 and confidence >= 70:
            final_signal = "SELL"
        else:
            final_signal = "HOLD"
            reasons.append("The composite score or confidence threshold is not strong enough to trade.")

        result = {
            "signal": final_signal,
            "confidence": round(confidence, 2),
            "strength": strength,
            "composite_score": round(composite, 4),
            "individual_scores": {key: round(value, 4) for key, value in scores.items()},
            "reasons": reasons,
        }
        print(
            f"[SignalGenerator] {final_signal} | score={composite:.4f} | "
            f"confidence={confidence:.2f}% | strength={strength}"
        )
        return result

    @staticmethod
    def _calculate_confidence(scores: Mapping[str, float], composite: float) -> float:
        """Estimate agreement confidence from weighted directional agreement.

        A score of zero is neutral and does not count as agreement. The
        resulting mapping intentionally follows the requested bands:
        unanimous agreement approaches 95%, mixed signals land near 50%, and
        mostly contrary signals approach 20%.
        """
        weighted_total = sum(abs(score) * SignalGenerator.INDICATOR_WEIGHTS[name] for name, score in scores.items())
        if weighted_total == 0:
            return 30.0
        direction = 1 if composite >= 0 else -1
        agreement = sum(
            SignalGenerator.INDICATOR_WEIGHTS[name]
            for name, score in scores.items()
            if score != 0 and np.sign(score) == direction
        )
        # Map 0..1 agreement to 10..100, while keeping neutral weak signals
        # from being mistaken for unanimous confirmation.
        confidence = 10.0 + agreement * 90.0
        return float(np.clip(confidence, 10.0, 100.0))

    @staticmethod
    def format_signal_report(signal_result: Mapping[str, Any]) -> str:
        """Format a generated result as a readable console/UI report."""
        if not isinstance(signal_result, Mapping):
            raise ValueError("signal_result must be a dictionary-like object.")
        scores = signal_result.get("individual_scores", {})
        reasons = signal_result.get("reasons", [])
        lines = [
            "=" * 56,
            "SMARTTRADER-AI SIGNAL REPORT",
            "=" * 56,
            f"Decision:         {signal_result.get('signal', 'UNKNOWN')}",
            f"Confidence:       {signal_result.get('confidence', 0):.2f}%",
            f"Strength:          {signal_result.get('strength', 'UNKNOWN')}",
            f"Composite score:  {signal_result.get('composite_score', 0):+.4f}",
            "",
            "Individual indicator scores:",
        ]
        for name in ("rsi", "macd", "bollinger", "volume", "trend"):
            lines.append(f"  {name.title():<12}: {float(scores.get(name, 0)):+.2f}")
        lines.extend(["", "Reasons:"])
        lines.extend(f"  - {reason}" for reason in reasons)
        lines.append("=" * 56)
        return "\n".join(lines)


__all__ = ["SignalGenerator"]
