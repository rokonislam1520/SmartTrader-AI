"""Read-only market sentiment analysis for SmartTrader-AI.

The module combines the public Alternative.me Fear & Greed Index with
CoinGecko's public trending-coins endpoint. It never requires credentials and
fails closed to a neutral sentiment when an upstream service is unavailable.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any, Dict, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class SentimentAnalyzer:
    """Fetch, normalize, and cache external crypto sentiment signals."""

    FEAR_GREED_URL = "https://api.alternative.me/fng/?limit=1"
    TRENDING_URL = "https://api.coingecko.com/api/v3/search/trending"
    CACHE_DURATION = timedelta(minutes=15)
    REQUEST_TIMEOUT_SECONDS = 10
    # Alternative.me usually returns 10 coins. This cap keeps the score
    # stable if the upstream API ever changes its response size.
    EXPECTED_TRENDING_COUNT = 10

    def __init__(self, cache_duration: timedelta = CACHE_DURATION) -> None:
        """Create an analyzer with a configurable in-memory cache.

        Args:
            cache_duration: How long a successful analysis may be reused.

        Raises:
            ValueError: If the duration is not a non-negative timedelta.
        """
        if not isinstance(cache_duration, timedelta) or cache_duration < timedelta(0):
            raise ValueError("cache_duration must be a non-negative timedelta.")
        self.cache_duration = cache_duration
        self._cache: Optional[Tuple[datetime, Dict[str, Any]]] = None

    def _fetch_json(self, url: str, params: Optional[Dict[str, str]] = None) -> Any:
        """Fetch and decode one public JSON endpoint.

        Args:
            url: HTTPS endpoint to request.
            params: Optional query-string parameters.

        Returns:
            Decoded JSON payload.

        Raises:
            RuntimeError: If the request or JSON response is invalid.
        """
        query = f"?{urlencode(params)}" if params else ""
        request = Request(
            f"{url}{query}",
            headers={"Accept": "application/json", "User-Agent": "SmartTrader-AI/1.0"},
        )
        try:
            with urlopen(request, timeout=self.REQUEST_TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            raise RuntimeError(f"Sentiment API request failed: {exc}") from exc

    @staticmethod
    def _normalize_score(value: float) -> float:
        """Clamp a numeric sentiment score to the inclusive range 0–100."""
        if not isfinite(value):
            return 50.0
        return max(0.0, min(100.0, float(value)))

    def _get_fear_greed(self) -> Tuple[float, str]:
        """Retrieve and validate the latest Alternative.me Fear & Greed value."""
        payload = self._fetch_json(self.FEAR_GREED_URL)
        rows = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            raise RuntimeError("Fear & Greed response did not contain data.")
        row = rows[0]
        try:
            value = self._normalize_score(float(row.get("value", 50)))
        except (TypeError, ValueError):
            value = 50.0
        classification = str(row.get("value_classification", "Neutral")).strip() or "Neutral"
        return value, classification

    def _get_trending(self) -> Tuple[int, float]:
        """Count CoinGecko trending coins and normalize count to 0–100."""
        payload = self._fetch_json(self.TRENDING_URL)
        coins = payload.get("coins") if isinstance(payload, dict) else None
        if not isinstance(coins, list):
            raise RuntimeError("CoinGecko response did not contain a coins list.")
        count = max(0, len(coins))
        # A full expected list maps to 100. Extra entries are safely capped.
        score = self._normalize_score((count / self.EXPECTED_TRENDING_COUNT) * 100)
        return count, score

    @staticmethod
    def _bias(score: float) -> str:
        """Map the overall score to the requested contrarian trading bias."""
        if score < 25:
            return "BUY"
        if score <= 45:
            return "BUY"
        if score <= 55:
            return "NEUTRAL"
        return "SELL"

    @staticmethod
    def _classification(score: float) -> str:
        """Return a stable human-readable classification for a score."""
        if score < 25:
            return "Extreme Fear"
        if score <= 45:
            return "Fear"
        if score <= 55:
            return "Neutral"
        if score <= 75:
            return "Greed"
        return "Extreme Greed"

    def _neutral_result(self) -> Dict[str, Any]:
        """Return a safe neutral result when either public API fails."""
        return {
            "fear_greed_value": 50.0,
            "fear_greed_classification": "Neutral",
            "trending_count": 0,
            "trending_score": 50.0,
            "sentiment_score": 50.0,
            "sentiment_bias": "NEUTRAL",
            "confidence": 0.0,
        }

    def analyze(self) -> Dict[str, Any]:
        """Combine Fear & Greed and trending data into one sentiment result.

        Returns:
            A dictionary with normalized values, bias, and confidence percentage.
            If either service fails, a neutral fail-safe result is returned.
        """
        now = datetime.now(timezone.utc)
        if self._cache and now - self._cache[0] < self.cache_duration:
            return dict(self._cache[1])
        try:
            fear_value, api_classification = self._get_fear_greed()
            trending_count, trending_score = self._get_trending()
            # Fear & Greed drives 60%; social discovery contributes 40%.
            sentiment_score = self._normalize_score(
                fear_value * 0.60 + trending_score * 0.40
            )
            result = {
                "fear_greed_value": round(fear_value, 2),
                "fear_greed_classification": self._classification(sentiment_score)
                if api_classification == ""
                else api_classification,
                "trending_count": trending_count,
                "trending_score": round(trending_score, 2),
                "sentiment_score": round(sentiment_score, 2),
                "sentiment_bias": self._bias(sentiment_score),
                # Agreement of two healthy sources gives a transparent baseline.
                "confidence": 80.0 if abs(fear_value - trending_score) <= 25 else 60.0,
            }
            self._cache = (now, result.copy())
            print("[SentimentAnalyzer] Sentiment analysis completed.")
            return result
        except Exception as exc:
            print(f"[SentimentAnalyzer] Using neutral fallback: {exc}")
            return self._neutral_result()


__all__ = ["SentimentAnalyzer"]
