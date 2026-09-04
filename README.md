# SmartTrader-AI 🤖

## AI-Powered Smart Trading Agent for Binance Agent OS Hackathon

SmartTrader-AI is a modular, safety-first trading research agent designed for the Binance Agent OS Hackathon. It combines market-data analysis, multi-indicator signal generation, and portfolio risk controls into one transparent workflow.

> **Demo safety notice:** The current entry runs in paper/demo mode. It prints hypothetical trade executions and does not submit live orders to Binance.

## Features ✅

- Multi-indicator analysis using RSI, MACD, Bollinger Bands, SMA, ATR, and volume
- Intelligent risk management with Kelly Criterion and dynamic ATR stop-losses
- Agent OS MCP execution path prepared for future integration
- Real-time public Binance market-data analysis
- Portfolio protection mechanisms and emergency-stop support
- Transparent confidence scores, risk scores, reasons, and formatted reports
- Modular Python architecture that separates analysis, signals, risk, and orchestration

## How It Works ⚙️

1. Fetches public candlestick market data from Binance.
2. Calculates five signal inputs: RSI, MACD, Bollinger Bands, volume confirmation, and SMA trend.
3. Generates `BUY`, `SELL`, or `HOLD` signals with weighted composite and confidence scores.
4. Validates directional trades against position limits, drawdown, daily loss, and risk/reward rules.
5. Calculates a risk-capped position size, stop-loss, and take-profit target.
6. Records a hypothetical position and prints a complete execution report.

## Risk Management 🛡️

- Maximum 2% risk per trade
- Half-Kelly Criterion position sizing with a hard risk cap
- Dynamic stop-loss based on 1.5× ATR
- Maximum stop-loss distance of 3% from entry
- Minimum 1:2 risk:reward ratio
- 10% maximum drawdown protection
- 5% daily loss limit
- Maximum 3 concurrent positions
- Emergency stop that disables future trade approvals
- Fail-closed validation for invalid or incomplete trade data

## Project Structure

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
├── main.py                   # Command-line entry point
└── requirements.txt          # Python dependencies
```

## Setup 📦

1. Clone this repository:

   ```bash
   git clone <your-repository-url>
   cd SmartTrader-AI
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Create your local environment file:

   ```bash
   # macOS/Linux
   cp .env.example .env

   # Windows PowerShell
   Copy-Item .env.example .env
   ```

4. Add your Binance API keys to `.env` if future authenticated features require them. Public market analysis currently does not require credentials. Keep real secrets out of Git.

5. Run the demo:

   ```bash
   python main.py
   ```

The default configuration uses Binance testnet settings and a paper balance of `10000`. The application performs one analysis cycle for each configured trading pair and then prints final status.

## Configuration

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

## Tech Stack 💻

- Python 3.9+
- Binance Agent OS
- pandas and NumPy
- `ta` technical-analysis library
- Binance public market-data API
- Agent OS MCP integration path

## Responsible Use

This project is a hackathon demonstration and is not financial advice. Cryptocurrency markets are volatile, and automated strategies can lose money. Test thoroughly with paper or testnet data, use appropriate credentials and permissions, and never expose API secrets or enable withdrawals for an unreviewed system.

## Author 👨‍💻

[Your Name]
