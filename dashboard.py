"""Streamlit dark dashboard for read-only SmartTrader-AI monitoring."""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

try:
    import streamlit as st
except ImportError:  # pragma: no cover - dashboard dependency is optional
    st = None  # type: ignore

from agent.market_analyzer import MarketAnalyzer
from agent.risk_manager import RiskManager
from agent.signal_generator import SignalGenerator
from config.settings import TRADING_PAIRS

try:
    import plotly.graph_objects as go
except ImportError:  # pragma: no cover - charting is optional
    go = None  # type: ignore


def render_dashboard() -> None:
    """Render live public market analysis without placing orders."""
    if st is None:
        raise RuntimeError("Dashboard dependencies are not installed. Run pip install streamlit plotly.")
    st.set_page_config(page_title="SmartTrader-AI", layout="wide", initial_sidebar_state="expanded")
    st.markdown("<style>body,.stApp{background:#0e1117;color:#e6edf3}.stMetric{background:#161b22;padding:12px;border-radius:8px}</style>", unsafe_allow_html=True)
    st.title("SmartTrader-AI Dashboard")
    st.caption("Read-only public Binance data. Dashboard never places live orders.")
    timeframe = st.sidebar.selectbox("Timeframe", ["15m", "1h", "4h", "1d"], index=1)
    refresh = st.sidebar.slider("Refresh seconds", 60, 600, 60)
    st.sidebar.caption(f"Auto-refresh configured: {refresh}s")
    analyzer = MarketAnalyzer()
    signals: List[Dict[str, Any]] = []
    for symbol in TRADING_PAIRS or ("BTCUSDT", "ETHUSDT"):
        try:
            analysis = analyzer.analyze_market(symbol, timeframe)
            signal = SignalGenerator().generate_signal(analysis)
            signals.append({"symbol": symbol, "analysis": analysis, "signal": signal})
        except Exception as exc:
            st.warning(f"{symbol} unavailable: {exc}")
    if not signals:
        st.error("No market data is currently available.")
        return
    cols = st.columns(len(signals))
    for col, item in zip(cols, signals):
        analysis, signal = item["analysis"], item["signal"]
        with col:
            st.metric(item["symbol"], f"${analysis['current_price']:,.2f}", signal["signal"])
            st.metric("Confidence", f"{signal['confidence']:.1f}%")
            st.write(f"Trend: **{analysis['trend_direction']}** | Volatility: **{analysis['volatility']}**")
            st.write("\n".join(f"- {reason}" for reason in signal["reasons"][:3]))
            try:
                candles = analyzer._fetch_klines(item["symbol"], timeframe)
                chart = pd.DataFrame(candles, columns=["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore"])
                chart["time"] = pd.to_datetime(chart["open_time"], unit="ms")
                chart["close"] = pd.to_numeric(chart["close"])
                if go is not None:
                    figure = go.Figure(go.Scatter(x=chart["time"], y=chart["close"], mode="lines", name=item["symbol"], line={"color": "#00d4aa"}))
                    figure.update_layout(height=260, margin={"l": 0, "r": 0, "t": 10, "b": 0}, template="plotly_dark")
                    st.plotly_chart(figure, use_container_width=True, config={"displayModeBar": False})
                else:
                    st.line_chart(chart.set_index("time")["close"])
            except Exception as exc:
                st.caption(f"Chart unavailable: {exc}")

    st.subheader("Indicators and signal history")
    if "signal_history" not in st.session_state:
        st.session_state["signal_history"] = []
    st.session_state["signal_history"].extend({"symbol": item["symbol"], "signal": item["signal"]["signal"], "confidence": item["signal"]["confidence"]} for item in signals)
    st.dataframe(st.session_state["signal_history"][-20:], use_container_width=True, hide_index=True)
    risk = RiskManager(initial_balance=10_000)
    health = risk.check_portfolio_health(10_000, 10_000, 0)
    st.subheader("Portfolio / risk")
    st.dataframe([health], use_container_width=True, hide_index=True)
    st.info("History is session-only in this read-only dashboard; no trades are submitted.")


if __name__ == "__main__":
    render_dashboard()
