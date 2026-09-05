"""Optional Telegram notifications with a credential-safe no-op mode."""

from typing import Any, Mapping, Optional
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


class TelegramNotifier:
    """Send formatted trading notifications, or silently no-op when disabled."""

    def __init__(self, token: str = TELEGRAM_BOT_TOKEN, chat_id: str = TELEGRAM_CHAT_ID) -> None:
        self.token = token.strip()
        self.chat_id = chat_id.strip()
        self.enabled = bool(self.token and self.chat_id)

    def send_message(self, text: str) -> bool:
        """Send text through python-telegram-bot when available, otherwise HTTPS."""
        if not self.enabled:
            return False
        try:
            try:
                from telegram import Bot  # type: ignore
                import asyncio
                asyncio.run(Bot(self.token).send_message(chat_id=self.chat_id, text=text))
            except ImportError:
                payload = urlencode({"chat_id": self.chat_id, "text": text}).encode()
                request = Request(
                    f"https://api.telegram.org/bot{self.token}/sendMessage",
                    data=payload, method="POST",
                )
                with urlopen(request, timeout=10) as response:
                    if response.status >= 300:
                        return False
            return True
        except Exception as exc:
            print(f"[TelegramNotifier] Notification failed: {exc}")
            return False

    def signal(self, symbol: str, signal: Mapping[str, Any]) -> bool:
        """Send a concise signal report."""
        return self.send_message(
            f"SmartTrader-AI SIGNAL\n{symbol}: {signal.get('signal', 'UNKNOWN')}\n"
            f"Confidence: {float(signal.get('confidence', 0)):.2f}%\n"
            f"Score: {float(signal.get('composite_score', 0)):+.4f}"
        )

    def trade(self, trade: Mapping[str, Any]) -> bool:
        """Send an executed or simulated trade notification."""
        return self.send_message(
            f"SmartTrader-AI TRADE\n{trade.get('side', trade.get('signal', 'UNKNOWN'))} "
            f"{trade.get('symbol', '')}\nPrice: {trade.get('entry_price', 'n/a')}\n"
            f"Quantity: {trade.get('quantity', 'n/a')}"
        )

    def emergency(self, reason: str) -> bool:
        """Send an emergency-stop alert."""
        return self.send_message(f"SmartTrader-AI EMERGENCY STOP\n{reason}")

    def daily_summary(self, summary: Mapping[str, Any]) -> bool:
        """Send a daily portfolio summary."""
        return self.send_message(
            "SmartTrader-AI DAILY SUMMARY\n"
            + "\n".join(f"{key}: {value}" for key, value in summary.items())
        )


__all__ = ["TelegramNotifier"]
