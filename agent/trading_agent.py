"""Main orchestration layer for the SmartTrader-AI demo trading agent."""

import math
import os
from datetime import datetime
from typing import Any, Dict, List, Optional


class BinanceMCPError(RuntimeError):
    """Raised when the configured Binance Agent OS MCP client is unavailable."""

from agent.market_analyzer import MarketAnalyzer
from agent.multi_timeframe import MultiTimeframeAnalyzer
from agent.signal_generator import SignalGenerator
from agent.risk_manager import RiskManager
from agent.report_generator import ReportGenerator
from agent.sentiment_analyzer import SentimentAnalyzer
from config.settings import BINANCE_TESTNET, MAX_RISK_PER_TRADE, TRADING_PAIRS
from utils.notifier import TelegramNotifier


class TradingAgent:
    """Coordinate market analysis, signals, risk controls, and Binance MCP calls."""

    def __init__(self, initial_balance: Optional[float] = None, mcp_client: Any = None) -> None:
        """Initialize modules and an optional authenticated MCP client.

        ``mcp_client`` should be the connected Binance Agent OS MCP client.
        It is injected rather than fabricated here because MCP SDK clients
        differ by host. The client must expose ``call_tool(name, arguments)``.
        """
        raw_balance = os.getenv("ACCOUNT_BALANCE", "10000") if initial_balance is None else initial_balance
        try:
            self.initial_balance = float(raw_balance)
        except (TypeError, ValueError) as exc:
            raise ValueError("Initial balance must be numeric.") from exc
        if not math.isfinite(self.initial_balance) or self.initial_balance <= 0:
            raise ValueError("Initial balance must be a finite number greater than zero.")

        self.balance = self.initial_balance
        self.market_analyzer = MarketAnalyzer()
        self.signal_generator = SignalGenerator()
        self.multi_timeframe_analyzer = MultiTimeframeAnalyzer(
            market_analyzer=self.market_analyzer,
            signal_generator=self.signal_generator,
        )
        self.risk_manager = RiskManager(initial_balance=self.initial_balance)
        self.sentiment_analyzer = SentimentAnalyzer()
        self.report_generator = ReportGenerator()
        self.notifier = TelegramNotifier()
        self.mcp_client = mcp_client
        self.execution_mode = "MCP" if mcp_client is not None else "DEMO"
        self.binance_connected = False
        self.account_balance: Dict[str, Any] = {"total": self.balance, "free": self.balance}
        self.open_positions: List[Dict[str, Any]] = []
        self.daily_pnl = 0.0
        self.is_running = False
        self._cycle_results: List[Dict[str, Any]] = []

        print(f"[TradingAgent] Initialized in {self.execution_mode} mode ({'TESTNET' if BINANCE_TESTNET else 'PUBLIC API'}).")

    def _call_binance_mcp(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a Binance MCP tool through the host-provided client.

        Tool names are centralized here so the integration can be adapted to
        the exact server schema without spreading MCP details across the agent.
        """
        if self.mcp_client is None:
            raise BinanceMCPError(
                "No Binance MCP client configured. Pass the authenticated "
                "binance-mcp-server client as mcp_client."
            )
        caller = getattr(self.mcp_client, "call_tool", None)
        if not callable(caller):
            raise BinanceMCPError("MCP client must provide call_tool(name, arguments).")
        try:
            return caller(tool_name, arguments)
        except Exception as exc:
            raise BinanceMCPError(f"Binance MCP tool '{tool_name}' failed: {exc}") from exc

    def connect_to_binance(self) -> bool:
        """Use MCP when available, otherwise activate public-API DEMO mode."""
        if self.mcp_client is None:
            self.execution_mode = "DEMO"
            self.binance_connected = True
            print("[TradingAgent] MCP not available; DEMO mode uses Binance public API.")
            return True

        try:
            self._call_binance_mcp("binance_get_account", {})
            self.binance_connected = True
            self.execution_mode = "MCP"
            print("[TradingAgent] Binance MCP connection verified.")
            return True
        except BinanceMCPError as exc:
            self.mcp_client = None
            self.execution_mode = "DEMO"
            self.binance_connected = True
            print(f"[TradingAgent] MCP unavailable ({exc}); falling back to DEMO mode.")
            return True

    def get_account_balance(self) -> Dict[str, Any]:
        """Return MCP account balance or the local demo balance."""
        if self.execution_mode == "DEMO":
            print(f"[TradingAgent] DEMO balance: {self.balance:.2f}")
            return dict(self.account_balance)
        try:
            response = self._call_binance_mcp("binance_get_account", {})
            self.account_balance = response if isinstance(response, dict) else {"raw": response}
            total = self.account_balance.get("total")
            if isinstance(total, (int, float)) and total > 0:
                self.balance = float(total)
            print(f"[TradingAgent] Account balance received: {self.account_balance}")
            return dict(self.account_balance)
        except BinanceMCPError as exc:
            print(f"[TradingAgent] Balance MCP call failed; retaining DEMO balance: {exc}")
            self.execution_mode = "DEMO"
            return dict(self.account_balance)

    def place_order(self, symbol: str, side: str, quantity: float) -> Any:
        """Place through MCP, or print a non-live demo order.

        Args:
            symbol: Binance symbol to trade.
            side: ``BUY`` or ``SELL``.
            quantity: Positive base-asset quantity.

        Raises:
            ValueError: If the symbol, side, or quantity is invalid.
            BinanceMCPError: If live-mode prerequisites are not met.
        """
        normalized_symbol = str(symbol).strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol cannot be empty.")
        normalized_side = str(side).strip().upper()
        if normalized_side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL.")
        try:
            normalized_quantity = float(quantity)
        except (TypeError, ValueError) as exc:
            raise ValueError("quantity must be numeric.") from exc
        if not math.isfinite(normalized_quantity) or normalized_quantity <= 0:
            raise ValueError("quantity must be a finite number greater than zero.")
        if self.execution_mode == "DEMO":
            result = {"mode": "DEMO", "symbol": normalized_symbol, "side": normalized_side, "quantity": normalized_quantity}
            print(f"[TradingAgent] DEMO TRADE: {normalized_side} {normalized_symbol} x {normalized_quantity}")
            return result
        if not self.binance_connected:
            raise BinanceMCPError("Connect to Binance before placing an order.")
        try:
            result = self._call_binance_mcp(
                "binance_place_order",
                {"symbol": normalized_symbol, "side": normalized_side, "quantity": normalized_quantity, "type": "MARKET"},
            )
            print(f"[TradingAgent] MCP order placed: {normalized_side} {normalized_symbol} x {normalized_quantity}")
            return result
        except BinanceMCPError as exc:
            print(f"[TradingAgent] Order MCP call failed; switching to DEMO: {exc}")
            self.execution_mode = "DEMO"
            return self.place_order(symbol, normalized_side, quantity)

    def get_live_market_data(self, symbol: str) -> Dict[str, Any]:
        """Use MCP ticker data, or Binance's public 24-hour ticker in DEMO mode."""
        normalized_symbol = str(symbol).strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol cannot be empty.")
        if self.execution_mode != "DEMO":
            try:
                response = self._call_binance_mcp("binance_get_ticker", {"symbol": normalized_symbol})
                print(f"[TradingAgent] Live market data received via MCP for {normalized_symbol}.")
                return response if isinstance(response, dict) else {"raw": response}
            except BinanceMCPError as exc:
                print(f"[TradingAgent] Ticker MCP call failed; using public API: {exc}")
                self.execution_mode = "DEMO"

        try:
            import json
            from urllib.parse import urlencode
            from urllib.request import Request, urlopen

            query = urlencode({"symbol": normalized_symbol})
            request = Request(
                f"https://api.binance.com/api/v3/ticker/24hr?{query}",
                headers={"User-Agent": "SmartTrader-AI/1.0"},
            )
            with urlopen(request, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Public Binance ticker response was not an object.")
            print(f"[TradingAgent] Public Binance market data received for {normalized_symbol}.")
            return payload
        except Exception as exc:
            print(f"[TradingAgent] Public market data failed for {normalized_symbol}: {exc}")
            return {"symbol": normalized_symbol, "error": str(exc)}

    @staticmethod
    def _apply_sentiment_to_signal(signal: Dict[str, Any], sentiment: Dict[str, Any]) -> Dict[str, Any]:
        """Apply the requested sentiment override/conflict rules to a signal."""
        result = dict(signal)
        bias = str(sentiment.get("sentiment_bias", "NEUTRAL")).upper()
        original = str(result.get("signal", "HOLD")).upper()
        try:
            confidence = max(0.0, min(100.0, float(result.get("confidence", 0.0))))
        except (TypeError, ValueError):
            confidence = 0.0
        if original == "HOLD" and bias in {"BUY", "SELL"} and confidence > 50:
            result["signal"] = bias
            result.setdefault("reasons", []).append(
                f"Sentiment bias {bias} upgraded the HOLD signal."
            )
        elif original in {"BUY", "SELL"} and bias in {"BUY", "SELL"} and original != bias:
            confidence = max(0.0, confidence - 10.0)
            result.setdefault("reasons", []).append(
                f"Conflicting sentiment bias {bias} reduced confidence by 10%."
            )
        result["confidence"] = round(confidence, 2)
        result["sentiment_bias"] = bias
        result["original_signal"] = original
        result["strength"] = (
            "STRONG" if confidence >= 80 else "MODERATE" if confidence >= 60 else "WEAK"
        )
        return result

    def analyze_and_trade(self, symbol: str) -> Dict[str, Any]:
        """Analyze one symbol and record a hypothetical trade if approved."""
        symbol = symbol.strip().upper()
        print(f"\n[TradingAgent] Processing {symbol}...")

        try:
            # Step 1: obtain current indicators and market state.
            analysis = self.market_analyzer.analyze_market(symbol)
            multi_timeframe = self.multi_timeframe_analyzer.analyze(symbol)
            print(
                f"[TradingAgent] Multi-timeframe: {multi_timeframe['combined_signal']} | "
                f"confidence={multi_timeframe['confidence']:.2f}% | "
                f"agreement={multi_timeframe['agreement_count']}/"
                f"{multi_timeframe['successful_timeframes']}"
            )

            # Step 2: add broad market sentiment as a transparent context signal.
            sentiment = self.sentiment_analyzer.analyze()
            print(
                f"[SentimentAnalyzer] Fear & Greed: {sentiment['fear_greed_value']:.0f} "
                f"({sentiment['fear_greed_classification']}) | "
                f"Trending: {sentiment['trending_count']} | "
                f"Bias: {sentiment['sentiment_bias']}"
            )

            # Step 3: create a transparent multi-indicator signal.
            signal = self.signal_generator.generate_signal(analysis)
            signal["signal"] = multi_timeframe["combined_signal"]
            signal["confidence"] = multi_timeframe["confidence"]
            signal["strength"] = (
                "STRONG" if signal["confidence"] >= 80
                else "MODERATE" if signal["confidence"] >= 60 else "WEAK"
            )
            signal["multi_timeframe"] = multi_timeframe
            signal.setdefault("reasons", []).append(
                f"Multi-timeframe signal: {multi_timeframe['combined_signal']} "
                f"({multi_timeframe['agreement_count']}/{multi_timeframe['successful_timeframes']} agreement)."
            )
            signal = self._apply_sentiment_to_signal(signal, sentiment)
            signal["sentiment"] = sentiment
            cycle_analysis = {
                "symbol": symbol,
                "sentiment": sentiment,
                "multi_timeframe": multi_timeframe,
                "technical": analysis,
                "signal": signal,
            }
            self.notifier.signal(symbol, signal)

            # Step 4: show the complete signal report.
            print(self.signal_generator.format_signal_report(signal))

            signal_name = signal["signal"]
            if signal_name == "HOLD":
                print(f"[TradingAgent] {symbol}: HOLD signal; trade skipped.")
                cycle_analysis["risk"] = {"status": "not evaluated for HOLD"}
                cycle_analysis["portfolio"] = self.risk_manager.check_portfolio_health(self.balance, self.initial_balance, self.daily_pnl)
                return {"symbol": symbol, "signal": signal, "status": "skipped", "reason": "HOLD signal", "report_data": cycle_analysis}

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
                cycle_analysis["risk"] = {"allowed": allowed, "reason": reason, "risk_score": risk_score}
                cycle_analysis["portfolio"] = self.risk_manager.check_portfolio_health(self.balance, self.initial_balance, self.daily_pnl)
                return {
                    "symbol": symbol, "signal": signal, "status": "rejected",
                    "reason": reason, "risk_score": risk_score, "report_data": cycle_analysis,
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
            self.notifier.trade(position)
            cycle_analysis["risk"] = {"allowed": allowed, "reason": reason, "risk_score": risk_score, "position_size": quantity}
            cycle_analysis["portfolio"] = self.risk_manager.check_portfolio_health(self.balance, self.initial_balance, self.daily_pnl)
            print(f"[TradingAgent] Position recorded. Open positions: {len(self.open_positions)}")
            return {"symbol": symbol, "signal": signal, "status": "executed", "position": position, "reason": reason, "report_data": cycle_analysis}
        except Exception as exc:
            # A failed pair must not prevent the remaining configured pairs.
            print(f"[TradingAgent] ERROR processing {symbol}: {exc}")
            return {"symbol": symbol, "status": "error", "reason": str(exc)}

    def run_single_cycle(self) -> List[Dict[str, Any]]:
        """Analyze every configured trading pair once and print a summary."""
        print("\n[TradingAgent] Starting single trading cycle...")
        self._cycle_results = [self.analyze_and_trade(pair) for pair in TRADING_PAIRS]
        report_data = {
            "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "symbols": list(TRADING_PAIRS),
            "sentiment": {"cycles": [r.get("report_data", {}).get("sentiment", {}) for r in self._cycle_results]},
            "multi_timeframe": {"cycles": [r.get("report_data", {}).get("multi_timeframe", {}) for r in self._cycle_results]},
            "technical": {"cycles": [r.get("report_data", {}).get("technical", {}) for r in self._cycle_results]},
            "signal": {"cycles": [r.get("report_data", {}).get("signal", r.get("signal", {})) for r in self._cycle_results]},
            "risk": {"cycles": [r.get("report_data", {}).get("risk", {}) for r in self._cycle_results]},
            "portfolio": {"balance": self.balance, "daily_pnl": self.daily_pnl, "open_positions": list(self.open_positions)},
        }
        report_text = self.report_generator.generate_text_report(report_data)
        report_name = f"trading_cycle_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.txt"
        report_path = self.report_generator.save_report(report_text, report_name)
        print(f"[TradingAgent] Report saved: {report_path}")

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
        """Verify MCP first, then run one analysis cycle."""
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
        if not self.connect_to_binance():
            # This branch is defensive; connect_to_binance currently activates
            # DEMO mode when MCP is absent or unavailable.
            self.is_running = False
            print("[TradingAgent] Unable to initialize Binance access; agent stopped safely.")
            return
        # Refresh the account balance when MCP provides one; DEMO keeps 10,000.
        self.get_account_balance()
        print(f"  Execution mode: {self.execution_mode}")
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
