"""Command-line entry point for SmartTrader-AI."""

from datetime import datetime
from typing import Any

from agent.trading_agent import TradingAgent
from config.settings import BINANCE_TESTNET, MAX_RISK_PER_TRADE, TRADING_PAIRS


def create_binance_mcp_client() -> Any:
    """Return an authenticated MCP client when Agent OS exposes one.

    MCP is optional. A missing package, unavailable server, or setup error
    returns ``None`` so the agent can safely continue with public API data.
    """
    try:
        from binance_mcp_client import get_authenticated_client

        client = get_authenticated_client(server_name="binance-mcp-server")
        if client is None:
            print("[main] Binance MCP unavailable; using DEMO mode.")
            return None
        print("[main] Binance MCP client loaded.")
        return client
    except Exception as exc:
        print(f"[main] Binance MCP unavailable ({exc}); using DEMO mode.")
        return None


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
    print("  Execution mode: MCP if available, otherwise DEMO")

    try:
        # Create the already-authenticated Agent OS client and inject it into
        # the coordinator. No API secret is read or handled by this script.
        mcp_client = create_binance_mcp_client()
        agent = TradingAgent(initial_balance=10000, mcp_client=mcp_client)
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
