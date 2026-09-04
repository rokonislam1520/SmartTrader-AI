"""Risk management and capital-preservation rules for SmartTrader-AI.

This module is intentionally defensive: invalid inputs fail closed, all risk
limits are enforced before a trade is approved, and an emergency stop cannot
be bypassed through normal validation.
"""

from datetime import date
from typing import Any, Dict, Mapping, Optional, Tuple

import numpy as np

from config.settings import (
    DAILY_LOSS_LIMIT,
    MAX_DRAWDOWN,
    MAX_POSITIONS,
    MAX_RISK_PER_TRADE,
    MIN_RISK_REWARD_RATIO,
    STOP_LOSS_ATR_MULTIPLIER,
)


class RiskManager:
    """Apply position-sizing, loss-limit, and trade-validation safeguards."""

    def __init__(self, initial_balance: Optional[float] = None) -> None:
        """Initialize risk state.

        Args:
            initial_balance: Optional positive baseline used for drawdown checks.

        Raises:
            ValueError: If ``initial_balance`` is supplied but invalid.
        """
        self.initial_balance = (
            self._non_negative(initial_balance, "initial_balance")
            if initial_balance is not None
            else None
        )
        self.daily_pnl = 0.0
        self.open_positions_count = 0
        self.maximum_drawdown = 0.0
        self._emergency_stop_active = False
        self._daily_stats_date = date.today()

    @staticmethod
    def _positive(value: Any, name: str) -> float:
        """Convert a value to a finite positive float; invalid data fails closed."""
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be a number.") from exc
        if not np.isfinite(number) or number <= 0:
            raise ValueError(f"{name} must be greater than zero.")
        return number

    @staticmethod
    def _non_negative(value: Any, name: str) -> float:
        """Convert a value to a finite non-negative float."""
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be a number.") from exc
        if not np.isfinite(number) or number < 0:
            raise ValueError(f"{name} must be non-negative.")
        return number

    def calculate_position_size(
        self,
        account_balance: float,
        entry_price: float,
        stop_loss_price: float,
        win_probability: float = 0.55,
        win_loss_ratio: float = 2.0,
    ) -> float:
        """Return coin quantity using a capped Kelly fraction.

        Kelly fraction is ``p - (1-p)/b``. It is deliberately reduced to a
        half-Kelly allocation for volatility control, then capped by the
        configured maximum risk percentage. The final quantity ensures that
        a stop-loss hit cannot lose more than MAX_RISK_PER_TRADE percent.
        """
        balance = self._positive(account_balance, "account_balance")
        entry = self._positive(entry_price, "entry_price")
        stop = self._positive(stop_loss_price, "stop_loss_price")
        if entry == stop:
            raise ValueError("Entry price and stop-loss price must differ.")
        probability = self._positive(win_probability, "win_probability")
        ratio = self._positive(win_loss_ratio, "win_loss_ratio")
        if probability >= 1:
            raise ValueError("win_probability must be between 0 and 1.")

        kelly_fraction = probability - ((1.0 - probability) / ratio)
        half_kelly = max(0.0, kelly_fraction * 0.5)
        max_risk_fraction = MAX_RISK_PER_TRADE / 100.0
        risk_fraction = min(half_kelly, max_risk_fraction)
        risk_capital = balance * risk_fraction
        risk_per_coin = abs(entry - stop)
        quantity = risk_capital / risk_per_coin
        print(f"[RiskManager] Position size: {quantity:.8f} coins; risk fraction: {risk_fraction:.4%}")
        return float(max(0.0, quantity))

    def calculate_stop_loss(self, entry_price: float, atr_value: float, direction: str) -> float:
        """Calculate an ATR stop, capped at a maximum 3% distance from entry."""
        entry = self._positive(entry_price, "entry_price")
        atr = self._positive(atr_value, "atr_value")
        side = direction.strip().lower()
        if side not in {"long", "short"}:
            raise ValueError("direction must be 'long' or 'short'.")

        # ATR distance adapts to volatility, while the 3% cap limits tail risk.
        distance = min(atr * STOP_LOSS_ATR_MULTIPLIER, entry * 0.03)
        return float(entry - distance if side == "long" else entry + distance)

    def calculate_take_profit(self, entry_price: float, stop_loss_price: float) -> float:
        """Return a 1:2-or-better target, on the opposite side of the stop."""
        entry = self._positive(entry_price, "entry_price")
        stop = self._positive(stop_loss_price, "stop_loss_price")
        if entry == stop:
            raise ValueError("Entry price and stop-loss price must differ.")
        risk = abs(entry - stop)
        # Infer direction from stop placement: below entry means a long trade.
        return float(entry + risk * MIN_RISK_REWARD_RATIO if stop < entry else entry - risk * MIN_RISK_REWARD_RATIO)

    def check_portfolio_health(
        self, current_balance: float, initial_balance: float, daily_pnl: float
    ) -> Dict[str, Any]:
        """Evaluate drawdown, daily loss, and concurrent-position limits."""
        current = self._non_negative(current_balance, "current_balance")
        initial = self._positive(initial_balance, "initial_balance")
        pnl = float(daily_pnl)
        if not np.isfinite(pnl):
            raise ValueError("daily_pnl must be finite.")
        drawdown_pct = max(0.0, (initial - current) / initial * 100.0)
        daily_loss_pct = max(0.0, -pnl / initial * 100.0)
        self.maximum_drawdown = max(self.maximum_drawdown, drawdown_pct)
        self.daily_pnl = pnl
        healthy = drawdown_pct < MAX_DRAWDOWN and daily_loss_pct < DAILY_LOSS_LIMIT
        return {
            "healthy": bool(healthy and not self._emergency_stop_active),
            "drawdown_percent": round(drawdown_pct, 4),
            "daily_loss_percent": round(daily_loss_pct, 4),
            "open_positions": self.open_positions_count,
            "max_positions": MAX_POSITIONS,
            "emergency_stop": self._emergency_stop_active,
        }

    def validate_trade(
        self,
        signal: Mapping[str, Any],
        account_balance: float,
        current_positions: Any,
        current_daily_pnl: float,
    ) -> Tuple[bool, str, int]:
        """Approve only trades that pass every portfolio and signal safeguard."""
        try:
            balance = self._positive(account_balance, "account_balance")
            positions = len(current_positions) if not isinstance(current_positions, (int, float)) else int(current_positions)
            if positions < 0:
                raise ValueError("current_positions cannot be negative.")
            self.open_positions_count = positions
            health = self.check_portfolio_health(balance, self.initial_balance or balance, current_daily_pnl)
            if self._emergency_stop_active:
                return False, "Emergency stop is active.", 10
            if health["drawdown_percent"] >= MAX_DRAWDOWN:
                return False, "Maximum portfolio drawdown reached.", 10
            if health["daily_loss_percent"] >= DAILY_LOSS_LIMIT:
                return False, "Daily loss limit reached.", 9
            if positions >= MAX_POSITIONS:
                return False, "Maximum concurrent positions reached.", 8

            if not isinstance(signal, Mapping):
                return False, "Invalid trade signal.", 8
            entry = self._positive(signal.get("entry_price"), "signal.entry_price")
            stop = self._positive(signal.get("stop_loss_price"), "signal.stop_loss_price")
            take_profit = self._positive(signal.get("take_profit_price"), "signal.take_profit_price")
            direction = str(signal.get("direction", "")).lower()
            if direction not in {"long", "short"}:
                return False, "Signal direction must be long or short.", 8
            if direction == "long" and not (stop < entry < take_profit):
                return False, "Long trade prices are not ordered correctly.", 8
            if direction == "short" and not (take_profit < entry < stop):
                return False, "Short trade prices are not ordered correctly.", 8

            risk_reward = abs(take_profit - entry) / abs(entry - stop)
            risk_score = int(np.clip(round(6.0 - min(risk_reward, 3.0)), 1, 10))
            if risk_reward < MIN_RISK_REWARD_RATIO:
                return False, "Risk/reward ratio is below the minimum.", max(7, risk_score)
            if risk_score > 7:
                return False, "Trade risk score is too high.", risk_score
            return True, f"Trade approved (risk/reward {risk_reward:.2f}:1).", risk_score
        except (TypeError, ValueError, KeyError) as exc:
            print(f"[RiskManager] Trade rejected: {exc}")
            return False, f"Invalid trade parameters: {exc}", 10

    def emergency_stop(self) -> None:
        """Immediately disable all future trade approvals."""
        self._emergency_stop_active = True
        print("[RiskManager] EMERGENCY STOP ACTIVE: all trading disabled.")

    def is_trading_allowed(self) -> bool:
        """Return whether the emergency-stop gate currently permits trading."""
        return not self._emergency_stop_active

    def reset_daily_stats(self) -> None:
        """Reset daily P&L tracking while retaining lifetime drawdown protection."""
        self.daily_pnl = 0.0
        self._daily_stats_date = date.today()
        print("[RiskManager] Daily risk statistics reset.")


__all__ = ["RiskManager"]
