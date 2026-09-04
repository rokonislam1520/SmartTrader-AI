"""Main orchestration layer for the SmartTrader-AI demo trading agent."""

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from agent.market_analyzer import MarketAnalyzer
from agent.signal_generator import SignalGenerator
from agent.risk_manager import RiskManager
from config.settings import BINANCE_TESTNET, MAX_RISK_PER_TRADE, TRADING_PAIRS


class TradingAgent:
    """Coordinate market analysis, signal generation, and risk controls.

    This implementation is deliberately demo-only: it prints hypothetical
    executions and never submits orders to Binance.
    """

    def __init__(self, initial_balance: Optional[float] = None) -> None:
        """Initialize modules and paper-trading state.

        The project settings do not define an account balance, so the optional
        argument or ACCOUNT_BALANCE environment variable is used; otherwise
        the safe paper-trading default is 10,000.
        """
        raw_balance = os.getenv("ACCOUNT_BALANCE", "10000") if initial_balance is None else initial_balance
        try:
            self.initial_balance = float(raw_balance)
        except (TypeError, ValueError) as exc:
            raise ValueError("Initial balance must be numeric.") from exc
        if self.initial_balance <= 0:
            raise ValueError("Initial balance must be greater than zero.")

        self.balance = self.initial_balance
        self.market_analyzer = MarketAnalyzer()
        self.signal_generator = SignalGenerator()
        self.risk_manager = RiskManager(initial_balance=self.initial_balance)
        self.open_positions: List[Dict[str, Any]] = []
        self.daily_pnl = 0.0
        self.is_running = False
        self._cycle_results: List[Dict[str, Any]] = []

        print(f"[TradingAgent] Initialized in {'TESTNET' if BINANCE_TESTNET else 'DEMO'} mode.")

    def analyze_and_trade(self, symbol: str) -> Dict[str, Any]:
        """Analyze one symbol and record a hypothetical trade if approved."""
        symbol = symbol.strip().upper()
        print(f"\n[TradingAgent] Processing {symbol}...")

        try:
            # Step 1: obtain current indicators and market state.
            analysis = self.market_analyzer.analyze_market(symbol)

            # Step 2: create a transparent multi-indicator signal.
            signal = self.signal_generator.generate_signal(analysis)

            # Step 3: show the complete signal report.
            print(self.signal_generator.format_signal_report(signal))

            signal_name = signal["signal"]
            if signal_name == "HOLD":
                print(f"[TradingAgent] {symbol}: HOLD signal; trade skipped.")
                return {"symbol": symbol, "signal": signal, "status": "skipped", "reason": "HOLD signal"}

            # Calculate prices before validation so the risk manager can check
            # direction, stop placement, and the required risk/reward ratio.
            direction = "long" if signal_name == "BUY" else "short"
            entry_price = float(analysis["current_price"])
            stop_loss = self.risk_manager.calculate_stop_loss(
                entry_price, float(analysis["atr_value"]), direction
            )
            take_profit = self.risk_manager.calculate_take_profit(entry_price, stop_loss)
            trade_signal = dict(signal)
            trade_signal.update({
                "direction": direction,
                "entry_price": entry_price,
                "stop_loss_price": stop_loss,
                "take_profit_price": take_profit,
            })

            # Step 4: enforce all portfolio and signal safety gates.
            allowed, reason, risk_score = self.risk_manager.validate_trade(
                trade_signal, self.balance, self.open_positions, self.daily_pnl
            )
            if not allowed:
                print(f"[TradingAgent] TRADE REJECTED for {symbol}: {reason}")
                return {
                    "symbol": symbol, "signal": signal, "status": "rejected",
                    "reason": reason, "risk_score": risk_score,
                }

            # Step 5: cap quantity so a stop-loss hit cannot exceed configured risk.
            quantity = self.risk_manager.calculate_position_size(
                self.balance, entry_price, stop_loss
            )

            # Step 6: demo execution only; no live order API is called.
            print(f"TRADE EXECUTED: {signal_name} {symbol} at {entry_price:.8f}")
            print(f"Quantity: {quantity:.8f}")
            print(f"Stop Loss: {stop_loss:.8f}")
            print(f"Take Profit: {take_profit:.8f}")
            print(f"Risk Score: {risk_score}")

            # Step 7: remember the hypothetical position for position limits.
            position = {
                "symbol": symbol,
                "side": signal_name,
                "direction": direction,
                "entry_price": entry_price,
                "quantity": quantity,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "risk_score": risk_score,
                "opened_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            }
            self.open_positions.append(position)
            print(f"[TradingAgent] Position recorded. Open positions: {len(self.open_positions)}")
            return {"symbol": symbol, "signal": signal, "status": "executed", "position": position, "reason": reason}
        except Exception as exc:
            # A failed pair must not prevent the remaining configured pairs.
            print(f"[TradingAgent] ERROR processing {symbol}: {exc}")
            return {"symbol": symbol, "status": "error", "reason": str(exc)}

    def run_single_cycle(self) -> List[Dict[str, Any]]:
        """Analyze every configured trading pair once and print a summary."""
        print("\n[TradingAgent] Starting single trading cycle...")
        self._cycle_results = [self.analyze_and_trade(pair) for pair in TRADING_PAIRS]

        print("\n" + "=" * 56)
        print("CYCLE SUMMARY")
        print("=" * 56)
        for result in self._cycle_results:
            signal = result.get("signal", {}).get("signal", "N/A")
            print(f"{result.get('symbol', 'UNKNOWN')}: {signal} -> {result.get('status', 'unknown')}")
        print(f"Open positions: {len(self.open_positions)}")
        print("=" * 56)
        return list(self._cycle_results)

    def start(self) -> None:
        """Print the startup banner and run one demo cycle."""
        self.is_running = True
        print("=" * 48)
        print("|   SmartTrader AI - Binance Agent OS          |")
        print("|   Hackathon Entry v1.0                       |")
        print("|   Status: RUNNING                            |")
        print("=" * 48)
        print("Configuration:")
        print(f"  Trading pairs: {', '.join(TRADING_PAIRS)}")
        print(f"  Testnet mode: {BINANCE_TESTNET}")
        print(f"  Paper balance: {self.balance:.2f}")
        print(f"  Max risk/trade: {MAX_RISK_PER_TRADE:.2f}%")
        print("  Execution: DEMO ONLY (no live orders)")
        self.run_single_cycle()

    def stop(self) -> None:
        """Stop future cycles while retaining recorded paper positions."""
        self.is_running = False
        print("Agent stopped")

    def get_status(self) -> Dict[str, Any]:
        """Return the current state for a dashboard or API response."""
        return {
            "is_running": self.is_running,
            "open_positions": len(self.open_positions),
            "daily_pnl": self.daily_pnl,
            "balance": self.balance,
        }


__all__ = ["TradingAgent"]
