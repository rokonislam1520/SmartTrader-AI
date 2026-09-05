"""Application configuration for the SmartTrader-AI Binance trading agent.

All values can be overridden through a ``.env`` file in the project root.
Never commit a real ``.env`` file or live Binance API credentials.
"""

import math
import os
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv


# Resolve the project root from this file so configuration works regardless
# of the directory from which the application is started.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_FILE)


def _get_bool(name: str, default: bool) -> bool:
    """Read a boolean environment variable using common true/false values.

    Args:
        name: Environment variable name.
        default: Value used when the variable is absent.

    Returns:
        The parsed boolean value.

    Raises:
        ValueError: If a present value is not a recognized boolean literal.
    """
    value = os.getenv(name)
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False

    raise ValueError(
        f"Invalid boolean value for {name!r}: {value!r}. "
        "Use true/false."
    )


# Binance credentials. These are required by validate_config().
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "").strip()
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "").strip()

# Telegram is optional; notifier methods become safe no-ops when unset.
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# Trading and risk-management settings.
BINANCE_TESTNET = _get_bool("BINANCE_TESTNET", True)
TRADING_PAIRS = tuple(
    pair.strip().upper()
    for pair in os.getenv("TRADING_PAIRS", "BTCUSDT,ETHUSDT").split(",")
    if pair.strip()
)
# Parse once at import time so the rest of the application can use typed constants.
try:
    MAX_RISK_PER_TRADE = float(os.getenv("MAX_RISK_PER_TRADE", "2.0"))
    DAILY_LOSS_LIMIT = float(os.getenv("DAILY_LOSS_LIMIT", "5.0"))
    MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", "3"))
    TRADE_INTERVAL = int(os.getenv("TRADE_INTERVAL", "900"))
    MAX_DRAWDOWN = float(os.getenv("MAX_DRAWDOWN", "10.0"))
    STOP_LOSS_ATR_MULTIPLIER = float(os.getenv("STOP_LOSS_ATR_MULTIPLIER", "1.5"))
    MIN_RISK_REWARD_RATIO = float(os.getenv("MIN_RISK_REWARD_RATIO", "2.0"))
except (TypeError, ValueError) as exc:
    raise ValueError("Numeric trading configuration contains an invalid value.") from exc


# Names that must have usable values before the agent can trade.
_REQUIRED_CONFIG_KEYS = (
    "BINANCE_API_KEY",
    "BINANCE_API_SECRET",
    "TRADING_PAIRS",
)


def validate_config() -> bool:
    """Validate required settings and basic risk/trading constraints.

    Returns:
        True when the configuration is valid.

    Raises:
        ValueError: If a required setting is missing or invalid.
    """
    missing_keys = [
        key
        for key in _REQUIRED_CONFIG_KEYS
        if not globals().get(key)
    ]
    if missing_keys:
        raise ValueError(
            "Missing required configuration value(s): "
            + ", ".join(missing_keys)
        )

    if not TRADING_PAIRS:
        raise ValueError("TRADING_PAIRS must contain at least one symbol.")
    numeric_values = (
        MAX_RISK_PER_TRADE,
        DAILY_LOSS_LIMIT,
        MAX_DRAWDOWN,
        STOP_LOSS_ATR_MULTIPLIER,
        MIN_RISK_REWARD_RATIO,
    )
    if any(not math.isfinite(value) or value <= 0 for value in numeric_values):
        raise ValueError("Risk-management values must be finite and greater than zero.")
    if MAX_POSITIONS < 1:
        raise ValueError("MAX_POSITIONS must be at least 1.")
    if TRADE_INTERVAL < 1:
        raise ValueError("TRADE_INTERVAL must be at least 1 second.")

    return True


def get_config() -> Dict[str, Any]:
    """Return all application settings as a dictionary."""
    return {
        "BINANCE_API_KEY": BINANCE_API_KEY,
        "BINANCE_API_SECRET": BINANCE_API_SECRET,
        "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
        "BINANCE_TESTNET": BINANCE_TESTNET,
        "TRADING_PAIRS": TRADING_PAIRS,
        "MAX_RISK_PER_TRADE": MAX_RISK_PER_TRADE,
        "DAILY_LOSS_LIMIT": DAILY_LOSS_LIMIT,
        "MAX_POSITIONS": MAX_POSITIONS,
        "TRADE_INTERVAL": TRADE_INTERVAL,
        "MAX_DRAWDOWN": MAX_DRAWDOWN,
        "STOP_LOSS_ATR_MULTIPLIER": STOP_LOSS_ATR_MULTIPLIER,
        "MIN_RISK_REWARD_RATIO": MIN_RISK_REWARD_RATIO,
    }


# Keep this visible during development so it is clear that no live orders
# should be sent while using the default configuration.
if BINANCE_TESTNET:
    print("WARNING: Binance Agent OS is running in TESTNET mode.")
