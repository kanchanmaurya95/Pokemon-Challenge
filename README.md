# Pokémon TCG AI Battle Challenge

A Python implementation of an AI Training Agent for the
[Pokémon TCG AI Battle Challenge](https://www.kaggle.com/competitions/pokemon-tcg-ai-battle-challenge)
Kaggle competition (Strategy Category).

---

## Overview

This project builds an end-to-end system for:

1. **Analysing** the competition card pool (EN/JP CSV datasets)
2. **Constructing** a 60-card deck using a data-driven, damage-per-energy metric
3. **Piloting** the deck with a greedy heuristic battle agent that targets opponent
   weaknesses and maximises prize card economy

The chosen archetype is a **Speed Aggro** deck that aims to knock out the
opponent's Pokémon on turns 1–3, before they can establish their own strategy.

---

## Repository Structure

```
Pokemon-Challenge/
├── src/
│   ├── __init__.py
│   ├── game_state.py      # Card / board state data models
│   ├── card_analyzer.py   # CSV loader + card pool analysis
│   ├── deck_builder.py    # Automated deck construction
│   └── battle_agent.py    # Greedy heuristic AI agent
├── notebooks/
│   └── analysis.py        # Run card pool analysis from the CLI
├── tests/
│   ├── test_game_state.py
│   ├── test_card_analyzer.py
│   ├── test_deck_builder.py
│   └── test_battle_agent.py
├── writeup/
│   └── strategy_writeup.md   # Kaggle Strategy Category writeup
├── data/                      # Place competition CSV files here
│   └── (EN Card Data.csv, JP Card Data.csv – download from Kaggle)
├── requirements.txt
└── README.md
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Download the dataset

Download the competition files from Kaggle and place them in the `data/` folder:

- `data/EN Card Data.csv`
- `data/JP Card Data.csv`

### 3. Run card pool analysis

```bash
python notebooks/analysis.py --csv "data/EN Card Data.csv"
```

This prints:
- Summary statistics (card counts, average HP, average damage, …)
- Type distribution chart
- Top-10 Pokémon ranked by damage-per-energy efficiency
- An auto-constructed 60-card deck listing

### 4. Run the tests

```bash
pytest tests/ -v
```

---

## Strategy Summary

| Component | Approach |
|-----------|----------|
| Deck type | Speed Aggro (Basic Pokémon, attack turn 1–2) |
| Card scoring | Damage-Per-Energy (DPE) metric |
| Type selection | Auto-select highest average DPE across top-5 Basics |
| Trainer ratio | 28 Trainers (8 Supporters / 16 Items / 4 Stadiums) |
| Energy count | 14 Basic Energy |
| Agent logic | Greedy heuristic scoring: KO > Weakness > Attach > Draw > Bench |
| Evaluation | Prize differential + HP advantage + energy readiness |

See [`writeup/strategy_writeup.md`](writeup/strategy_writeup.md) for the full
Kaggle Strategy Category writeup.

---

## Licence

This project is submitted under the competition's terms of participation.
Pokémon and all related names are trademarks of Nintendo / The Pokémon Company.