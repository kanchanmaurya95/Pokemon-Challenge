"""
Pokemon TCG Card Pool Analysis
Parses EN_Card_Data.csv to profile all cards by type, stage, HP, damage, cost, abilities.
Identifies top archetypes and strongest cards for deck construction.
"""

import pandas as pd
import numpy as np
import json
import os
import re
from collections import defaultdict

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "EN_Card_Data.csv")
OUTPUT_DIR = os.path.join(BASE_DIR, "analysis", "output")


def load_card_data():
    """Load and clean the card CSV data."""
    df = pd.read_csv(CSV_PATH)
    df.columns = [
        "card_id", "card_name", "expansion", "collection_no", "stage_type",
        "rule", "category", "previous_stage", "hp", "type", "weakness",
        "resistance", "retreat", "move_name", "cost", "damage", "effect"
    ]
    # Clean n/a values
    df.replace("n/a", np.nan, inplace=True)
    # Convert HP to numeric
    df["hp"] = pd.to_numeric(df["hp"], errors="coerce")
    # Convert retreat to numeric
    df["retreat"] = pd.to_numeric(df["retreat"], errors="coerce")
    return df


def parse_damage(damage_str):
    """Parse damage string to numeric value. Handles '30×', '100+', etc."""
    if pd.isna(damage_str):
        return 0
    damage_str = str(damage_str).strip()
    # Remove multiplier/plus symbols for base value
    clean = re.sub(r"[×x+\-]", "", damage_str)
    try:
        return int(clean)
    except ValueError:
        return 0


def count_energy_cost(cost_str):
    """Count total energy cost from cost string like {R}{R}● or ●●."""
    if pd.isna(cost_str):
        return 0
    cost_str = str(cost_str)
    # Count typed energy {X}
    typed = len(re.findall(r"\{[A-Z]\}", cost_str))
    # Count colorless ●
    colorless = cost_str.count("●")
    return typed + colorless


def classify_cards(df):
    """Classify cards into categories."""
    categories = {
        "basic_energy": df[df["stage_type"] == "Basic Energy"],
        "special_energy": df[df["stage_type"] == "Special Energy"],
        "basic_pokemon": df[df["stage_type"] == "Basic Pokémon"],
        "stage1_pokemon": df[df["stage_type"] == "Stage 1 Pokémon"],
        "stage2_pokemon": df[df["stage_type"] == "Stage 2 Pokémon"],
        "trainer": df[df["stage_type"].str.contains("Trainer|Supporter|Item|Stadium|Tool", na=False)],
    }
    return categories


def analyze_pokemon(df):
    """Analyze Pokemon cards for best damage-to-cost ratios."""
    pokemon_df = df[df["stage_type"].str.contains("Pokémon", na=False)].copy()
    pokemon_df["damage_num"] = pokemon_df["damage"].apply(parse_damage)
    pokemon_df["cost_num"] = pokemon_df["cost"].apply(count_energy_cost)
    pokemon_df["damage_per_cost"] = pokemon_df.apply(
        lambda r: r["damage_num"] / r["cost_num"] if r["cost_num"] > 0 else 0, axis=1
    )
    pokemon_df["has_ability"] = pokemon_df["move_name"].str.contains(r"\[Ability\]", na=False)
    pokemon_df["is_ex"] = pokemon_df["rule"].str.contains("ex", na=False)
    return pokemon_df


def identify_top_attackers(pokemon_df, top_n=30):
    """Find Pokemon with best damage output relative to cost."""
    attackers = pokemon_df[pokemon_df["damage_num"] > 0].copy()
    # Deduplicate by card_id, keep highest damage move
    best_moves = attackers.sort_values("damage_num", ascending=False).drop_duplicates("card_id")
    # Score: damage_per_cost weighted by HP sustainability
    best_moves["score"] = (
        best_moves["damage_per_cost"] * 0.5 +
        (best_moves["damage_num"] / 100) * 0.3 +
        (best_moves["hp"].fillna(0) / 300) * 0.2
    )
    return best_moves.nlargest(top_n, "score")[
        ["card_id", "card_name", "stage_type", "hp", "type", "move_name",
         "damage_num", "cost_num", "damage_per_cost", "score", "is_ex", "rule"]
    ]


def identify_support_pokemon(pokemon_df, top_n=20):
    """Find Pokemon with useful abilities."""
    ability_pokemon = pokemon_df[pokemon_df["has_ability"]].drop_duplicates("card_id")
    return ability_pokemon[
        ["card_id", "card_name", "stage_type", "hp", "type", "move_name", "effect"]
    ].head(top_n)


def analyze_trainers(df):
    """Analyze trainer cards for deck support."""
    trainers = df[df["stage_type"].str.contains("Trainer|Supporter|Item|Stadium|Tool", na=False)].copy()
    trainers = trainers.drop_duplicates("card_id")
    # Categorize by function based on effect text
    draw_cards = trainers[trainers["effect"].str.contains("draw|Draw", na=False)]
    search_cards = trainers[trainers["effect"].str.contains("search|Search|deck", na=False)]
    energy_accel = trainers[trainers["effect"].str.contains("attach|Energy", na=False)]
    disruption = trainers[trainers["effect"].str.contains("discard|shuffle|hand", na=False)]
    return {
        "draw": draw_cards[["card_id", "card_name", "effect"]],
        "search": search_cards[["card_id", "card_name", "effect"]],
        "energy_acceleration": energy_accel[["card_id", "card_name", "effect"]],
        "disruption": disruption[["card_id", "card_name", "effect"]],
    }


def identify_archetypes(pokemon_df, df):
    """Identify viable deck archetypes based on card pool."""
    archetypes = []

    # 1. Basic ex Rush - high HP basics with strong attacks
    basic_ex = pokemon_df[
        (pokemon_df["stage_type"] == "Basic Pokémon") &
        (pokemon_df["is_ex"]) &
        (pokemon_df["damage_num"] >= 100)
    ].drop_duplicates("card_id")

    for ptype in basic_ex["type"].unique():
        type_cards = basic_ex[basic_ex["type"] == ptype]
        if len(type_cards) >= 1:
            archetypes.append({
                "name": f"Basic {ptype} Ex Rush",
                "strategy": "Fast aggressive with high-HP basic ex attackers",
                "key_cards": type_cards["card_name"].tolist()[:3],
                "type": ptype,
                "tier": "aggressive",
                "card_count": len(type_cards)
            })

    # 2. Stage 2 Control - evolution lines with powerful finishers
    stage2 = pokemon_df[
        (pokemon_df["stage_type"] == "Stage 2 Pokémon") &
        (pokemon_df["damage_num"] >= 150)
    ].drop_duplicates("card_id")

    for ptype in stage2["type"].unique():
        type_cards = stage2[stage2["type"] == ptype]
        if len(type_cards) >= 1:
            archetypes.append({
                "name": f"Stage 2 {ptype} Control",
                "strategy": "Evolution-based with powerful late-game attacks",
                "key_cards": type_cards["card_name"].tolist()[:3],
                "type": ptype,
                "tier": "control",
                "card_count": len(type_cards)
            })

    # 3. Spread damage - cards that hit bench
    spread = pokemon_df[
        pokemon_df["effect"].str.contains("damage counter|Benched|damage to", na=False)
    ].drop_duplicates("card_id")
    if len(spread) >= 2:
        archetypes.append({
            "name": "Spread Damage",
            "strategy": "Distribute damage across opponent's board for multi-KOs",
            "key_cards": spread["card_name"].tolist()[:5],
            "type": "multi",
            "tier": "spread",
            "card_count": len(spread)
        })

    return archetypes


def generate_meta_report(df, pokemon_df, archetypes, top_attackers, trainers):
    """Generate a full meta analysis report."""
    report = {
        "total_cards": int(df["card_id"].nunique()),
        "total_pokemon": int(pokemon_df["card_id"].nunique()),
        "by_stage": {
            "basic": int(pokemon_df[pokemon_df["stage_type"] == "Basic Pokémon"]["card_id"].nunique()),
            "stage1": int(pokemon_df[pokemon_df["stage_type"] == "Stage 1 Pokémon"]["card_id"].nunique()),
            "stage2": int(pokemon_df[pokemon_df["stage_type"] == "Stage 2 Pokémon"]["card_id"].nunique()),
        },
        "by_type": pokemon_df.drop_duplicates("card_id")["type"].value_counts().to_dict(),
        "ex_pokemon_count": int(pokemon_df[pokemon_df["is_ex"]]["card_id"].nunique()),
        "archetypes": archetypes,
        "top_attackers": top_attackers.to_dict(orient="records"),
        "trainer_categories": {k: len(v) for k, v in trainers.items()},
    }
    return report


def main():
    """Run full card pool analysis."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Loading card data...")
    df = load_card_data()
    print(f"Loaded {len(df)} rows, {df['card_id'].nunique()} unique cards")

    print("Analyzing Pokemon cards...")
    pokemon_df = analyze_pokemon(df)

    print("Identifying top attackers...")
    top_attackers = identify_top_attackers(pokemon_df)

    print("Identifying support Pokemon...")
    support = identify_support_pokemon(pokemon_df)

    print("Analyzing trainer cards...")
    trainers = analyze_trainers(df)

    print("Identifying archetypes...")
    archetypes = identify_archetypes(pokemon_df, df)

    print("Generating meta report...")
    report = generate_meta_report(df, pokemon_df, archetypes, top_attackers, trainers)

    # Save outputs
    report_path = os.path.join(OUTPUT_DIR, "meta_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"Meta report saved to {report_path}")

    # Save top attackers
    top_attackers.to_csv(os.path.join(OUTPUT_DIR, "top_attackers.csv"), index=False)

    # Print summary
    print("\n" + "=" * 60)
    print("CARD POOL ANALYSIS SUMMARY")
    print("=" * 60)
    print(f"Total unique cards: {report['total_cards']}")
    print(f"Total Pokemon: {report['total_pokemon']}")
    print(f"  Basic: {report['by_stage']['basic']}")
    print(f"  Stage 1: {report['by_stage']['stage1']}")
    print(f"  Stage 2: {report['by_stage']['stage2']}")
    print(f"  Ex Pokemon: {report['ex_pokemon_count']}")
    print(f"\nViable archetypes found: {len(archetypes)}")
    for arch in archetypes[:10]:
        print(f"  - {arch['name']}: {arch['strategy']}")
        print(f"    Key cards: {', '.join(arch['key_cards'][:3])}")
    print(f"\nTop 5 Attackers (by efficiency score):")
    for _, row in top_attackers.head(5).iterrows():
        print(f"  - {row['card_name']} ({row['stage_type']}): "
              f"{row['damage_num']} dmg / {row['cost_num']} cost = {row['damage_per_cost']:.1f} ratio")

    return report


if __name__ == "__main__":
    main()
