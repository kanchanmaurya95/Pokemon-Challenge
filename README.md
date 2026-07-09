# Pokemon TCG AI Battle Challenge

AI Training Agent for the Pokémon Trading Card Game (TCG) competition on Kaggle.

## Project Structure

```
├── analysis/               # Card pool analysis scripts
│   ├── card_analysis.py    # Parse & profile all cards, identify archetypes
│   └── output/             # Generated analysis reports (auto-updated daily)
├── agent/                  # AI Training Agent
│   ├── pokemon_agent.py    # Decision engine with phase-aware strategy
│   └── deck_config.json    # Deck list and strategy configuration
├── scripts/
│   └── daily_runner.py     # Daily pipeline runner
├── .github/workflows/
│   └── daily_run.yml       # GitHub Actions - runs analysis daily at 06:00 UTC
├── EN_Card_Data.csv        # English card metadata (2,102 entries)
├── JP_Card_Data.csv        # Japanese card metadata
└── requirements.txt        # Python dependencies
```

## Quick Start

```bash
pip install -r requirements.txt
python scripts/daily_runner.py
```

## Strategy: Turbo Basic-Ex Aggro

**Win Condition:** Take 6 prizes quickly with efficient Basic Pokémon-ex attackers before the opponent sets up.

**Key Cards:**
- Bloodmoon Ursaluna ex (260 HP, colorless attacker)
- Gouging Fire ex (230 HP, Ancient fire attacker)
- Iron Thorns ex (230 HP, shuts down opponent abilities)
- Morpeko (energy acceleration from discard)

## Daily Automated Runs

GitHub Actions runs the analysis pipeline daily at 06:00 UTC:
- Re-profiles the card pool
- Validates deck configuration
- Generates updated reports in `analysis/output/`

Trigger manually: Actions → Daily Pokemon TCG AI Run → Run workflow

## Competition

- **Simulation Category**: AI agent win rate and performance
- **Strategy Category**: Written analysis of approach (≤2000 words)
- **Deadline**: September 13, 2026