# Contributing to SmartTrader-AI

Thank you for helping improve SmartTrader-AI. Contributions should keep the project transparent, safety-first, and reproducible.

## Before You Start

- Read the README and understand the DEMO/MCP execution boundary.
- Open an issue for substantial features or behavior changes before implementation.
- Never commit `.env`, API keys, trading credentials, account data, or other secrets.
- Do not test against a live account. Use DEMO mode or Binance testnet only.

## Local Setup

```bash
git clone <your-repository-url>
cd SmartTrader-AI
python -m venv .venv

# macOS/Linux
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env  # Windows PowerShell
python main.py
```

Keep local credentials in `.env`; the file is ignored by Git and must not be shared.

## Development Guidelines

- Preserve existing public APIs and the default DEMO behavior.
- Keep MCP integration injectable and fail safely to DEMO when unavailable.
- Prefer small, focused changes with docstrings, type hints, and comments for non-obvious logic.
- Validate external data and configuration at boundaries; reject malformed values safely.
- Do not claim performance results without a reproducible methodology and evidence.
- Add or update tests when changing indicators, signals, risk rules, configuration, or execution paths.

## Style

- Target Python 3.9+ compatibility.
- Follow PEP 8, use descriptive names, and keep functions focused.
- Use four spaces for indentation and type annotations for public functions.
- Keep output and error messages actionable without exposing secrets.
- Use Markdown headings and fenced code blocks consistently in documentation.

## Validation

Before opening a pull request, run:

```bash
python -m py_compile agent/*.py config/*.py main.py utils/*.py
```

Also run the available tests and manually verify the safe DEMO path when practical. Include the commands run and their results in your pull request description.

## Pull Requests

1. Create a focused branch from the default branch.
2. Make the smallest complete change that addresses the issue.
3. Review the diff for secrets, generated files, and unrelated edits.
4. Explain behavior changes, edge cases, and validation steps.
5. Request review and respond to feedback constructively.

By contributing, you agree that your work may be distributed under the project's MIT License.
