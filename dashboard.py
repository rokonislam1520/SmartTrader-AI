"""Streamlit dark dashboard for read-only SmartTrader-AI monitoring."""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

try:
    import streamlit as st
except ImportError:  # pragma: no cover - dashboard dependency is optional
    st = None  # type: ignore

from agent.market_analyzer import MarketAnalyzer
from agent.multi_timeframe import MultiTimeframeAnalyzer
from agent.report_generator import ReportGenerator
from agent.risk_manager import RiskManager
from agent.sentiment_analyzer import SentimentAnalyzer
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
    multi_timeframe_analyzer = MultiTimeframeAnalyzer(
        market_analyzer=analyzer,
        signal_generator=SignalGenerator(),
    )
    sentiment_analyzer = SentimentAnalyzer()
    report_generator = ReportGenerator()
    sentiment = sentiment_analyzer.analyze()
    st.subheader("Market Sentiment")
    fear_value = float(sentiment["fear_greed_value"])
    fear_color = "#00d4aa" if fear_value > 55 else "#ff4b4b" if fear_value < 45 else "#f0b90b"
    bias = sentiment["sentiment_bias"]
    bias_color = "#00d4aa" if bias == "BUY" else "#ff4b4b" if bias == "SELL" else "#f0b90b"
    sentiment_cols = st.columns(4)
    sentiment_cols[0].markdown(
        f"<h3 style='color:{fear_color}'>Fear & Greed: {fear_value:.0f}</h3>"
        f"<p>{sentiment['fear_greed_classification']}</p>",
        unsafe_allow_html=True,
    )
    sentiment_cols[1].metric("Trending coins", sentiment["trending_count"])
    sentiment_cols[2].metric("Overall score", f"{sentiment['sentiment_score']:.1f}/100")
    sentiment_cols[3].markdown(
        f"<h3 style='color:{bias_color}'>Bias: {bias}</h3>", unsafe_allow_html=True
    )
    st.progress(max(0.0, min(1.0, float(sentiment["sentiment_score"]) / 100.0)))

    signals: List[Dict[str, Any]] = []
    for symbol in TRADING_PAIRS or ("BTCUSDT", "ETHUSDT"):
        try:
            analysis = analyzer.analyze_market(symbol, timeframe)
            signal = SignalGenerator().generate_signal(analysis)
            multi_timeframe = multi_timeframe_analyzer.analyze(symbol)
            signals.append({
                "symbol": symbol,
                "analysis": analysis,
                "signal": signal,
                "multi_timeframe": multi_timeframe,
            })
        except Exception as exc:
            st.warning(f"{symbol} unavailable: {exc}")
    if not signals:
        st.error("No market data is currently available.")
        return
    cols = st.columns(len(signals))
    for col, item in zip(cols, signals):
        analysis, signal = item["analysis"], item["signal"]
        multi_timeframe = item["multi_timeframe"]
        with col:
            st.metric(item["symbol"], f"${analysis['current_price']:,.2f}", signal["signal"])
            st.metric("Confidence", f"{signal['confidence']:.1f}%")
            st.write(f"Trend: **{analysis['trend_direction']}** | Volatility: **{analysis['volatility']}**")
            st.write("\n".join(f"- {reason}" for reason in signal["reasons"][:3]))
            st.subheader("Multi-Timeframe Analysis")
            mt_signal = multi_timeframe["combined_signal"]
            mt_color = "#00d4aa" if mt_signal == "BUY" else "#ff4b4b" if mt_signal == "SELL" else "#f0b90b"
            st.markdown(
                f"<h4 style='color:{mt_color}'>Combined: {mt_signal} "
                f"({multi_timeframe['confidence']:.1f}%)</h4>",
                unsafe_allow_html=True,
            )
            mt_cols = st.columns(3)
            for mt_col, mt_timeframe in zip(mt_cols, ("1h", "4h", "1d")):
                timeframe_result = multi_timeframe["timeframes"].get(mt_timeframe)
                if timeframe_result:
                    timeframe_signal = timeframe_result["signal"]
                    timeframe_color = "#00d4aa" if timeframe_signal == "BUY" else "#ff4b4b" if timeframe_signal == "SELL" else "#f0b90b"
                    mt_col.markdown(
                        f"<span style='color:{timeframe_color}'><b>{mt_timeframe}</b>: "
                        f"{timeframe_signal} ({timeframe_result['confidence']:.1f}%)</span>",
                        unsafe_allow_html=True,
                    )
                else:
                    mt_col.warning(f"{mt_timeframe}: unavailable")
            st.caption(
                f"Agreement: {multi_timeframe['agreement_count']}/"
                f"{multi_timeframe['successful_timeframes']}"
            )
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

    report_data = {
        "symbols": [item["symbol"] for item in signals],
        "sentiment": sentiment,
        "multi_timeframe": {item["symbol"]: item["multi_timeframe"] for item in signals},
        "technical": {item["symbol"]: item["analysis"] for item in signals},
        "signal": {item["symbol"]: item["signal"] for item in signals},
        "risk": health,
        "portfolio": {"balance": 10_000, "daily_pnl": 0, "open_positions": []},
    }
    if st.button("Generate Report"):
        report_text = report_generator.generate_text_report(report_data)
        filename = f"dashboard_report_{pd.Timestamp.utcnow().strftime('%Y%m%d_%H%M%S')}.txt"
        report_path = report_generator.save_report(report_text, filename)
        st.session_state["latest_report"] = report_text
        st.success(f"Report saved under reports: {report_path.name}")
    if st.session_state.get("latest_report"):
        st.subheader("Generated Report")
        st.text_area("Report", st.session_state["latest_report"], height=420)
    st.info("History is session-only in this read-only dashboard; no trades are submitted.")


if __name__ == "__main__":
    render_dashboard()
