"""Command-line entry point for SmartTrader-AI."""

from datetime import datetime

from agent.trading_agent import TradingAgent
from config.settings import BINANCE_TESTNET, MAX_RISK_PER_TRADE, TRADING_PAIRS


def print_banner() -> None:
    """Display the project banner used by the hackathon demo."""
    print("=" * 48)
    print("|   SmartTrader AI - Binance Agent OS          |")
    print("|   Hackathon Entry v1.0                       |")
    print("|   Status: RUNNING                            |")
    print("=" * 48)


def main() -> None:
    """Initialize and run one safe, demo-only trading cycle."""
    agent = None
    print_banner()
    print(f"Start time: {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print("Configuration:")
    print(f"  Trading pairs: {', '.join(TRADING_PAIRS)}")
    print(f"  Testnet mode: {BINANCE_TESTNET}")
    print(f"  Max risk per trade: {MAX_RISK_PER_TRADE}%")
    print("  Execution mode: DEMO ONLY")

    try:
        # The fixed paper balance keeps the hackathon entry deterministic.
        agent = TradingAgent(initial_balance=10000)
        agent.start()
        print("\nFinal status:")
        for key, value in agent.get_status().items():
            print(f"  {key}: {value}")
    except KeyboardInterrupt:
        print("\nShutdown requested. SmartTrader-AI stopped gracefully.")
        if agent is not None:
            agent.stop()
    except Exception as exc:
        print(f"\nSmartTrader-AI encountered an error: {exc}")
        if agent is not None:
            agent.stop()


if __name__ == "__main__":
    main()
