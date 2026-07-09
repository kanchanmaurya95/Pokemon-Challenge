"""
Pokémon TCG AI Battle Challenge – Card Pool Analysis Script

Run this script to generate analysis of the competition card data:

    python notebooks/analysis.py --csv data/EN\ Card\ Data.csv

Outputs summary statistics, type distributions, and the top-ranked
cards for deck construction.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from the repo root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.card_analyzer import CardAnalyzer, load_cards_from_csv
from src.deck_builder import DeckBuilder
from src.game_state import PokemonType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def print_section(title: str) -> None:
    width = 60
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)


def run_analysis(csv_path: str) -> None:
    print(f"Loading cards from: {csv_path}")
    cards = load_cards_from_csv(csv_path)
    analyzer = CardAnalyzer(cards)

    # ---- Summary statistics ----
    print_section("Card Pool Summary")
    analyzer.print_summary()

    # ---- Expansion distribution ----
    print_section("Cards Per Expansion")
    for expansion, count in analyzer.expansion_distribution().items():
        bar = "█" * (count // 5)
        print(f"  {expansion:<35} {count:>4}  {bar}")

    # ---- Weakness targeting ----
    print_section("Weakness Analysis (top 3 most common weaknesses)")
    type_weakness_counts: dict[str, int] = {}
    for ptype in PokemonType:
        targets = analyzer.weakness_targets(ptype)
        if targets:
            type_weakness_counts[ptype.value] = len(targets)
    sorted_weaknesses = sorted(
        type_weakness_counts.items(), key=lambda x: x[1], reverse=True
    )
    for ptype_name, count in sorted_weaknesses[:5]:
        print(f"  {ptype_name:<15} {count} Pokémon weak to this type")

    # ---- Low-retreat basics (ideal pivots) ----
    print_section("Zero-Retreat Basics (best pivot options)")
    for card in analyzer.low_retreat_basics(max_retreat=0)[:10]:
        bm = card.best_move
        dmg_str = f"  best move: {bm.name} ({bm.damage} dmg)" if bm else ""
        print(f"  {card.card_name:<30} HP={card.hp}{dmg_str}")

    # ---- Deck construction ----
    print_section("Automated Deck Construction")
    builder = DeckBuilder(analyzer)
    print(builder.explain())
    print()
    try:
        deck = builder.build()
        comp = deck.composition()
        print(f"Built deck: {deck}")
        print(f"  Pokémon : {comp['Pokémon']}")
        print(f"  Trainers: {comp['Trainer']}")
        print(f"  Energy  : {comp['Energy']}")
        print()
        print("  Card counts:")
        for name, count in deck.card_counts().items():
            print(f"    {count}x {name}")
    except Exception as exc:
        print(f"  Could not build a complete deck: {exc}")
        print("  (This is expected when not all card types are present in the CSV.)")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyse the Pokémon TCG competition card data."
    )
    parser.add_argument(
        "--csv",
        default="data/EN Card Data.csv",
        help="Path to the EN Card Data CSV file.",
    )
    args = parser.parse_args()

    csv_path = args.csv
    if not Path(csv_path).exists():
        print(f"CSV file not found: {csv_path!r}")
        print("Please download the dataset from Kaggle and place it in the data/ folder.")
        print("Expected location: data/EN Card Data.csv")
        sys.exit(1)

    run_analysis(csv_path)


if __name__ == "__main__":
    main()
