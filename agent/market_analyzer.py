"""Technical market analysis for the SmartTrader-AI trading agent.

This module retrieves public Binance candlestick data and converts it into a
small, decision-ready market analysis using the ``ta`` technical-analysis
library. No authenticated API credentials are required for market data.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import ta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from config.settings import TRADING_PAIRS

try:
    # The setting is optional so this module also works with older settings.py.
    from config.settings import BINANCE_TESTNET
except ImportError:
    BINANCE_TESTNET = True


class MarketAnalyzer:
    """Fetch Binance candles, calculate indicators, and cache analysis results."""

    CACHE_DURATION = timedelta(minutes=5)
    DEFAULT_LIMIT = 250  # Enough candles for the 200-period SMA.
    _BINANCE_SPOT_URL = "https://api.binance.com/api/v3/klines"
    _BINANCE_TESTNET_URL = "https://testnet.binance.vision/api/v3/klines"

    def __init__(self, cache_duration: timedelta = CACHE_DURATION) -> None:
        """Create an analyzer with an in-memory cache.

        Args:
            cache_duration: How long an analysis remains reusable. A negative
                duration is rejected because it would disable caching silently.
        """
        if not isinstance(cache_duration, timedelta) or cache_duration < timedelta(0):
            raise ValueError("cache_duration must be a non-negative timedelta.")
        self.cache_duration = cache_duration
        self._cache: Dict[Tuple[str, str], Tuple[datetime, Dict[str, Any]]] = {}

    def analyze_market(self, symbol: str, timeframe: str = "1h") -> Dict[str, Any]:
        """Return a complete technical analysis for ``symbol`` and ``timeframe``.

        Args:
            symbol: Binance symbol, for example ``BTCUSDT``.
            timeframe: Binance interval, for example ``1h`` or ``15m``.

        Returns:
            A dictionary containing the requested signals and indicator values.

        Raises:
            ValueError: If the symbol or timeframe is invalid.
            RuntimeError: If Binance data cannot be retrieved or analyzed.
        """
        normalized_symbol = symbol.strip().upper()
        normalized_timeframe = timeframe.strip()
        if not normalized_symbol:
            raise ValueError("Trading symbol cannot be empty.")
        if not normalized_timeframe:
            raise ValueError("Timeframe cannot be empty.")

        cache_key = (normalized_symbol, normalized_timeframe)
        now = datetime.utcnow()
        cached = self._cache.get(cache_key)
        if cached and now - cached[0] < self.cache_duration:
            print(f"[MarketAnalyzer] Using cached analysis for {normalized_symbol}.")
            return cached[1].copy()

        try:
            print(
                f"[MarketAnalyzer] Fetching {normalized_symbol} "
                f"({normalized_timeframe}) market data..."
            )
            candles = self._fetch_klines(normalized_symbol, normalized_timeframe)
            frame = self._build_dataframe(candles)
            analysis = self._calculate_analysis(frame)
            analysis.update(
                {
                    "symbol": normalized_symbol,
                    "timeframe": normalized_timeframe,
                    "analyzed_at": now.isoformat(timespec="seconds") + "Z",
                }
            )
            self._cache[cache_key] = (now, analysis.copy())
            print(f"[MarketAnalyzer] Analysis completed for {normalized_symbol}.")
            return analysis
        except (HTTPError, URLError, TimeoutError, ValueError, KeyError) as exc:
            print(f"[MarketAnalyzer] Market analysis failed: {exc}")
            raise RuntimeError(
                f"Unable to analyze {normalized_symbol}. Binance data may be unavailable."
            ) from exc
        except Exception as exc:
            # Keep unexpected failures from exposing internals in agent output.
            print(f"[MarketAnalyzer] Unexpected analysis error: {exc}")
            raise RuntimeError(f"Unexpected error analyzing {normalized_symbol}.") from exc

    def _fetch_klines(self, symbol: str, interval: str) -> List[List[Any]]:
        """Fetch public candlestick data from the configured Binance endpoint."""
        base_url = (
            self._BINANCE_TESTNET_URL if BINANCE_TESTNET else self._BINANCE_SPOT_URL
        )
        query = urlencode(
            {"symbol": symbol, "interval": interval, "limit": self.DEFAULT_LIMIT}
        )
        request = Request(
            f"{base_url}?{query}",
            headers={"User-Agent": "SmartTrader-AI/1.0"},
        )
        with urlopen(request, timeout=15) as response:
            import json

            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, list) or len(payload) < self.DEFAULT_LIMIT:
            raise ValueError("Binance returned insufficient candlestick data.")
        if any(not isinstance(row, (list, tuple)) or len(row) < 12 for row in payload):
            raise ValueError("Binance returned malformed candlestick rows.")
        return payload

    @staticmethod
    def _build_dataframe(candles: List[List[Any]]) -> pd.DataFrame:
        """Convert Binance kline rows into a clean OHLCV DataFrame."""
        columns = [
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades", "taker_buy_base",
            "taker_buy_quote", "ignore",
        ]
        frame = pd.DataFrame(candles, columns=columns)
        for column in ("open", "high", "low", "close", "volume"):
            frame[column] = pd.to_numeric(frame[column], errors="raise")
        if frame[["open", "high", "low", "close", "volume"]].isna().any().any():
            raise ValueError("Candlestick data contains missing numeric values.")
        return frame

    @staticmethod
    def _calculate_analysis(frame: pd.DataFrame) -> Dict[str, Any]:
        """Calculate indicators and map their values to trading statuses."""
        close = frame["close"]
        high = frame["high"]
        low = frame["low"]
        volume = frame["volume"]

        # ta provides the canonical implementations of each requested metric.
        rsi = ta.momentum.RSIIndicator(close=close, window=14).rsi()
        macd_indicator = ta.trend.MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
        macd = macd_indicator.macd()
        macd_signal = macd_indicator.macd_signal()
        bollinger = ta.volatility.BollingerBands(close=close, window=20, window_dev=2)
        bb_high = bollinger.bollinger_hband()
        bb_mid = bollinger.bollinger_mavg()
        bb_low = bollinger.bollinger_lband()
        sma20 = ta.trend.SMAIndicator(close=close, window=20).sma_indicator()
        sma50 = ta.trend.SMAIndicator(close=close, window=50).sma_indicator()
        sma200 = ta.trend.SMAIndicator(close=close, window=200).sma_indicator()
        atr = ta.volatility.AverageTrueRange(high=high, low=low, close=close, window=14).average_true_range()

        values = [rsi.iloc[-1], macd.iloc[-1], macd_signal.iloc[-1], bb_high.iloc[-1], bb_mid.iloc[-1], bb_low.iloc[-1], sma20.iloc[-1], sma50.iloc[-1], sma200.iloc[-1], atr.iloc[-1]]
        if not np.isfinite(values).all():
            raise ValueError("Not enough valid data to calculate all indicators.")

        price = float(close.iloc[-1])
        rsi_value = float(rsi.iloc[-1])
        macd_value = float(macd.iloc[-1])
        macd_signal_value = float(macd_signal.iloc[-1])
        atr_value = float(atr.iloc[-1])
        average_volume = float(volume.rolling(20).mean().iloc[-1])
        volume_ratio = float(volume.iloc[-1] / average_volume) if average_volume else 1.0

        if price >= float(bb_high.iloc[-1]):
            bollinger_position = "upper"
        elif price <= float(bb_low.iloc[-1]):
            bollinger_position = "lower"
        else:
            bollinger_position = "middle"

        if float(sma20.iloc[-1]) > float(sma50.iloc[-1]) > float(sma200.iloc[-1]):
            trend_direction = "up"
        elif float(sma20.iloc[-1]) < float(sma50.iloc[-1]) < float(sma200.iloc[-1]):
            trend_direction = "down"
        else:
            trend_direction = "sideways"

        atr_percent = (atr_value / price) * 100 if price else 0.0
        volatility = "high" if atr_percent >= 3 else "medium" if atr_percent >= 1 else "low"
        volume_status = "above_average" if volume_ratio > 1.2 else "below_average" if volume_ratio < 0.8 else "normal"

        # Include raw indicator values too, making the result useful for UI/debugging.
        return {
            "current_price": price,
            "rsi_value": round(rsi_value, 4),
            "rsi_status": "overbought" if rsi_value > 70 else "oversold" if rsi_value < 30 else "neutral",
            "macd_signal": "bullish" if macd_value > macd_signal_value else "bearish",
            "bollinger_position": bollinger_position,
            "trend_direction": trend_direction,
            "volatility": volatility,
            "volume_status": volume_status,
            "atr_value": round(atr_value, 8),
            "indicators": {
                "macd": round(macd_value, 8),
                "macd_signal": round(macd_signal_value, 8),
                "bollinger_upper": round(float(bb_high.iloc[-1]), 8),
                "bollinger_middle": round(float(bb_mid.iloc[-1]), 8),
                "bollinger_lower": round(float(bb_low.iloc[-1]), 8),
                "sma_20": round(float(sma20.iloc[-1]), 8),
                "sma_50": round(float(sma50.iloc[-1]), 8),
                "sma_200": round(float(sma200.iloc[-1]), 8),
                "volume_ratio": round(volume_ratio, 4),
                "atr_percent": round(atr_percent, 4),
            },
        }


__all__ = ["MarketAnalyzer", "TRADING_PAIRS"]
