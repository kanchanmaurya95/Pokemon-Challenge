"""
Daily Runner - Executes card analysis and agent evaluation.
Designed to be triggered by GitHub Actions on a daily schedule.
"""

import sys
import os
import json
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.card_analysis import main as run_analysis


def run_daily():
    """Run daily analysis and agent evaluation pipeline."""
    print(f"{'='*60}")
    print(f"POKEMON TCG AI - DAILY RUN")
    print(f"Date: {datetime.now(timezone.utc).isoformat()}")
    print(f"{'='*60}\n")

    # Step 1: Card Analysis
    print("[1/3] Running card pool analysis...")
    try:
        report = run_analysis()
        print(f"✓ Analysis complete. {report['total_cards']} cards profiled.\n")
    except Exception as e:
        print(f"✗ Analysis failed: {e}\n")
        report = None

    # Step 2: Agent Status
    print("[2/3] Checking agent configuration...")
    deck_config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "agent", "deck_config.json"
    )
    if os.path.exists(deck_config_path):
        with open(deck_config_path) as f:
            deck = json.load(f)
        print(f"✓ Deck loaded: {deck['name']}")
        print(f"  Strategy: {deck['strategy']}")
        print(f"  Total cards: {deck['total_cards']}")
        pokemon_count = sum(p["count"] for p in deck["deck_list"]["pokemon"])
        trainer_count = sum(t["count"] for t in deck["deck_list"]["trainers"])
        energy_count = sum(e["count"] for e in deck["deck_list"]["energy"])
        print(f"  Pokemon: {pokemon_count} | Trainers: {trainer_count} | Energy: {energy_count}")
        actual_total = pokemon_count + trainer_count + energy_count
        if actual_total != 60:
            print(f"  ⚠ Warning: Deck has {actual_total} cards (should be 60)")
        print()
    else:
        print("✗ No deck configuration found.\n")

    # Step 3: Summary
    print("[3/3] Generating daily summary...")
    summary = {
        "date": datetime.now(timezone.utc).isoformat(),
        "analysis_complete": report is not None,
        "deck_configured": os.path.exists(deck_config_path),
        "archetypes_identified": len(report["archetypes"]) if report else 0,
        "top_attacker": report["top_attackers"][0]["card_name"] if report and report["top_attackers"] else "N/A",
    }

    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "analysis", "output"
    )
    os.makedirs(output_dir, exist_ok=True)
    summary_path = os.path.join(output_dir, "daily_summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"✓ Daily summary saved to {summary_path}")
    print(f"\n{'='*60}")
    print("DAILY RUN COMPLETE")
    print(f"{'='*60}")

    return summary


if __name__ == "__main__":
    run_daily()
