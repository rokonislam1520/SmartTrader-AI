# SmartTrader-AI 🤖

<div align="center">

## 🧠 AI-Powered, Safety-First Trading Research Agent

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Binance Agent OS Hackathon](https://img.shields.io/badge/Binance-Agent%20OS%20Hackathon-F0B90B?logo=binance&logoColor=white)](https://www.binance.com/)

**Analyze markets. Explain signals. Control risk. Demonstrate safely.**

⭐ If SmartTrader-AI is useful or interesting, please [star the repository](../../stargazers) and share your feedback.

</div>

SmartTrader-AI is a modular, transparent trading research agent created for the Binance Agent OS Hackathon. It combines public Binance market data, multi-indicator signal generation, and portfolio risk controls into one inspectable workflow.

> **Demo safety notice:** The default entry point runs in paper/DEMO mode. It prints hypothetical trade executions and does not submit live orders to Binance. An optional host-provided MCP client can be injected for Agent OS integration; review and secure any authenticated integration before use.

## ✨ Features

- Multi-indicator analysis using RSI, MACD, Bollinger Bands, SMA, ATR, and volume
- Transparent `BUY`, `SELL`, or `HOLD` decisions with weighted scores and reasons
- Half-Kelly position sizing with a hard maximum-risk cap
- Dynamic ATR stop-losses, take-profit targets, and risk/reward validation
- Drawdown, daily-loss, concurrent-position, and emergency-stop protection
- Binance public market-data analysis without requiring credentials
- Optional Binance Agent OS MCP execution path with safe DEMO fallback
- Modular Python architecture separating analysis, signals, risk, and orchestration

## ⚡ Quick Demo

```bash
python main.py
```

Illustrative console output (values and decisions vary with live market data):

```text
================================================
|   SmartTrader AI - Binance Agent OS          |
|   Hackathon Entry v1.0                       |
|   Status: RUNNING                            |
================================================
[main] Binance MCP unavailable; using DEMO mode.
[TradingAgent] DEMO balance: 10000.00
[SignalGenerator] HOLD | score=0.1250 | confidence=70.50% | strength=MODERATE
BTCUSDT: HOLD -> skipped
ETHUSDT: BUY -> executed
Open positions: 1

Final status:
  is_running: True
  open_positions: 1
  daily_pnl: 0.0
  balance: 10000.0
```

The sample output is illustrative only and is not a measured performance result or a guarantee of execution.

## ⚙️ How It Works

1. Fetches public candlestick market data from Binance.
2. Calculates RSI, MACD, Bollinger Bands, volume confirmation, SMA trend, and ATR.
3. Generates a `BUY`, `SELL`, or `HOLD` signal with weighted composite and confidence scores.
4. Validates directional trades against position limits, drawdown, daily loss, and risk/reward rules.
5. Calculates a risk-capped position size, stop-loss, and take-profit target.
6. Records a hypothetical position and prints a complete execution report.

## 🛡️ Risk Controls

- Maximum 2% risk per trade
- Half-Kelly Criterion position sizing with a hard risk cap
- Dynamic stop-loss based on 1.5× ATR
- Maximum stop-loss distance of 3% from entry
- Minimum 1:2 risk/reward ratio
- 10% maximum drawdown protection
- 5% daily loss limit
- Maximum 3 concurrent positions
- Emergency stop that disables future trade approvals
- Fail-closed validation for invalid or incomplete trade data

## 📊 Performance Metrics

The following are **indicative/demo targets and design objectives**, not fabricated measured claims. This repository does not claim a live win rate, return, latency, Sharpe ratio, or production uptime. Results depend on market conditions, data quality, configuration, and execution environment.

| Metric | Indicative/demo target | Meaning |
|---|---:|---|
| Risk per trade | ≤ 2% | Hard portfolio-risk budget used by the demo |
| Minimum risk/reward | ≥ 2:1 | Trade approval threshold |
| Maximum drawdown gate | 10% | Safety threshold before new trades are rejected |
| Daily loss gate | 5% | Daily loss threshold before new trades are rejected |
| Concurrent positions | 3 max | Exposure-control objective |
| Analysis cache window | 5 minutes | Avoids redundant indicator requests |

For meaningful evaluation, add a reproducible backtest with a fixed data range, fees, slippage, and clearly stated methodology before comparing results.

## 📁 Project Structure

```text
SmartTrader-AI/
├── agent/
│   ├── market_analyzer.py    # Binance candles and technical indicators
│   ├── signal_generator.py   # Weighted BUY/SELL/HOLD decisions
│   ├── risk_manager.py       # Position sizing and safety controls
│   └── trading_agent.py      # Main module coordinator
├── config/
│   └── settings.py           # Environment-backed configuration
├── .env.example              # Configuration template
├── CONTRIBUTING.md           # Contribution and development guide
├── LICENSE                   # MIT license
├── main.py                   # Command-line entry point
└── requirements.txt          # Python dependencies
```

## 📦 Setup

1. Clone the repository and enter it:

   ```bash
   git clone <your-repository-url>
   cd SmartTrader-AI
   ```

2. Install dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

3. Create your local environment file without committing it:

   ```powershell
   Copy-Item .env.example .env
   ```

4. Add credentials only if a future authenticated feature requires them. Public market analysis does not require credentials. Never expose API secrets and never enable withdrawals for an unreviewed system.

5. Run the safe demo:

   ```bash
   python main.py
   ```

The default configuration uses Binance testnet settings and a paper balance of `10000`. The application performs one analysis cycle for each configured trading pair and then prints final status.

## 🔧 Configuration

The following values can be configured in `.env`:

| Variable | Default | Description |
|---|---:|---|
| `BINANCE_TESTNET` | `true` | Uses testnet market-data endpoint |
| `TRADING_PAIRS` | `BTCUSDT,ETHUSDT` | Comma-separated symbols |
| `MAX_RISK_PER_TRADE` | `2` | Maximum portfolio risk percentage |
| `DAILY_LOSS_LIMIT` | `5` | Daily loss threshold percentage |
| `MAX_POSITIONS` | `3` | Maximum concurrent paper positions |
| `TRADE_INTERVAL` | `900` | Future cycle interval in seconds |
| `MAX_DRAWDOWN` | `10.0` | Maximum portfolio drawdown percentage |
| `STOP_LOSS_ATR_MULTIPLIER` | `1.5` | ATR multiplier for stop placement |
| `MIN_RISK_REWARD_RATIO` | `2.0` | Minimum target-to-risk ratio |

## 💻 Tech Stack

- Python 3.9+
- Binance Agent OS / MCP integration path
- pandas and NumPy
- `ta` technical-analysis library
- Binance public market-data API

## 🚀 Future Improvements

- Add reproducible historical backtesting with fees, slippage, and walk-forward validation
- Add structured tests for indicators, risk gates, MCP adapters, and malformed API responses
- Add persistent paper-trading state and audit logs
- Add monitoring dashboards, alerts, and configurable circuit breakers
- Formalize the Binance Agent OS MCP adapter against the host's exact tool schema
- Add portfolio correlation, liquidity, and position-concentration controls

## 🤝 Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening an issue or pull request. Start with DEMO/testnet behavior, include tests or a clear validation note, and never include `.env`, API keys, or other credentials in a contribution.

## ⚠️ Responsible Use

This project is a hackathon demonstration and is not financial advice. Cryptocurrency markets are volatile, and automated strategies can lose money. Test thoroughly with paper or testnet data, use least-privilege credentials, and independently review all code before connecting any live account.

## 👨‍💻 Author

**Rokon** — [@rokonislam1520](https://github.com/rokonislam1520)

## 📄 License

SmartTrader-AI is released under the [MIT License](LICENSE). Copyright © 2026 Rokon (@rokonislam1520).
