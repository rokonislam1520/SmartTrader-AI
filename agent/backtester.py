"""Risk-aware, public-data-only Binance backtester for SmartTrader-AI."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from agent.market_analyzer import MarketAnalyzer
from agent.risk_manager import RiskManager
from agent.signal_generator import SignalGenerator


class Backtester:
    """Download public Binance candles and simulate the existing signal logic."""

    URL = "https://api.binance.com/api/v3/klines"

    def __init__(self, initial_balance: float = 10_000.0, fee_rate: float = 0.001, slippage: float = 0.0005) -> None:
        self.initial_balance = float(initial_balance)
        self.fee_rate = float(fee_rate)
        self.slippage = float(slippage)
        self.signal_generator = SignalGenerator()

    def download_history(self, symbol: str, interval: str = "1h", days: int = 30) -> pd.DataFrame:
        """Fetch up to ``days`` of public spot klines without authenticated APIs."""
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)
        rows: List[List[Any]] = []
        cursor = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)
        while cursor < end_ms:
            query = urlencode({"symbol": symbol.upper(), "interval": interval, "limit": 1000, "startTime": cursor, "endTime": end_ms})
            request = Request(f"{self.URL}?{query}", headers={"User-Agent": "SmartTrader-AI/1.0"})
            with urlopen(request, timeout=20) as response:
                import json as _json
                batch = _json.loads(response.read().decode("utf-8"))
            if not isinstance(batch, list) or not batch:
                break
            rows.extend(batch)
            cursor = int(batch[-1][6]) + 1
            if len(batch) < 1000:
                break
        if not rows:
            raise RuntimeError(f"No Binance history returned for {symbol}.")
        frame = MarketAnalyzer._build_dataframe(rows).copy()
        frame["timestamp"] = pd.to_datetime(frame["open_time"], unit="ms", utc=True)
        return frame.drop_duplicates("timestamp").reset_index(drop=True)

    def run(self, symbol: str = "BTCUSDT", interval: str = "1h", days: int = 30) -> Dict[str, Any]:
        """Run a paper simulation; no orders or authenticated endpoints are used."""
        frame = self.download_history(symbol, interval, days)
        balance = self.initial_balance
        equity_curve: List[float] = []
        trades: List[Dict[str, Any]] = []
        position: Optional[Dict[str, float]] = None
        risk = RiskManager(initial_balance=self.initial_balance)
        for index in range(250, len(frame)):
            window = frame.iloc[index - 250:index + 1]
            analysis = MarketAnalyzer._calculate_analysis(window)
            signal = self.signal_generator.generate_signal(analysis)
            price = float(frame.iloc[index]["close"])
            if position:
                hit_stop = (position["direction"] == 1 and float(frame.iloc[index]["low"]) <= position["stop"]) or (position["direction"] == -1 and float(frame.iloc[index]["high"]) >= position["stop"])
                hit_target = (position["direction"] == 1 and float(frame.iloc[index]["high"]) >= position["target"]) or (position["direction"] == -1 and float(frame.iloc[index]["low"]) <= position["target"])
                reverse = (position["direction"] == 1 and signal["signal"] == "SELL") or (position["direction"] == -1 and signal["signal"] == "BUY")
                if hit_stop or hit_target or reverse:
                    exit_price = position["stop"] if hit_stop else position["target"] if hit_target else price
                    pnl = (exit_price - position["entry"]) * position["quantity"] * position["direction"]
                    pnl -= abs(exit_price * position["quantity"]) * (self.fee_rate + self.slippage)
                    balance += pnl
                    trades.append({"entry": position["entry"], "exit": exit_price, "pnl": round(pnl, 4), "reason": "stop" if hit_stop else "target" if hit_target else "reverse"})
                    position = None
            if position is None and signal["signal"] in {"BUY", "SELL"}:
                direction = 1 if signal["signal"] == "BUY" else -1
                stop = risk.calculate_stop_loss(price, float(analysis["atr_value"]), "long" if direction == 1 else "short")
                target = risk.calculate_take_profit(price, stop)
                quantity = risk.calculate_position_size(balance, price, stop)
                position = {"direction": float(direction), "entry": price, "stop": stop, "target": target, "quantity": quantity}
            mark = price if position is None else position["entry"] + (price - position["entry"]) * position["direction"]
            equity_curve.append(balance + (0 if position is None else (mark - position["entry"]) * position["quantity"]))
        if position:
            final_price = float(frame.iloc[-1]["close"])
            balance += (final_price - position["entry"]) * position["quantity"] * position["direction"]
        curve = pd.Series(equity_curve or [balance])
        returns = curve.pct_change().dropna()
        wins = [trade["pnl"] for trade in trades if trade["pnl"] > 0]
        losses = [trade["pnl"] for trade in trades if trade["pnl"] <= 0]
        peak = curve.cummax()
        drawdown = ((curve - peak) / peak * 100).min()
        metrics = {"symbol": symbol.upper(), "interval": interval, "days": days, "initial_balance": self.initial_balance, "final_balance": round(balance, 2), "return_percent": round((balance / self.initial_balance - 1) * 100, 2), "trades": len(trades), "win_rate_percent": round(len(wins) / len(trades) * 100, 2) if trades else 0.0, "profit_factor": round(sum(wins) / abs(sum(losses)), 3) if losses and sum(losses) else None, "max_drawdown_percent": round(float(drawdown), 2), "sharpe_annualized": round(float(returns.mean() / returns.std() * (24 * 365) ** 0.5), 3) if len(returns) > 1 and returns.std() else 0.0}
        return {"metrics": metrics, "trades": trades, "equity": [round(float(value), 2) for value in equity_curve]}


def main() -> None:
    """CLI entry point for a safe, public-data-only backtest."""
    parser = argparse.ArgumentParser(description="Run SmartTrader-AI paper backtest")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--interval", default="1h")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--balance", type=float, default=10_000.0)
    args = parser.parse_args()
    result = Backtester(initial_balance=args.balance).run(args.symbol, args.interval, args.days)
    print(json.dumps(result["metrics"], indent=2))


if __name__ == "__main__":
    main()
