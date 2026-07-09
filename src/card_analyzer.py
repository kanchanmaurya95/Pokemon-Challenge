"""
Card data analysis module for the Pokémon TCG AI Battle Challenge.

Reads the EN/JP Card Data CSV files provided by Kaggle and exposes
helper methods for exploring the card pool, computing aggregate
statistics, and ranking cards by various metrics.
"""

from __future__ import annotations

import csv
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.game_state import (
    Card,
    CardCategory,
    EnergySubtype,
    Move,
    PokemonType,
    TrainerSubtype,
)


# ---------------------------------------------------------------------------
# CSV → Card parsing helpers
# ---------------------------------------------------------------------------


def _parse_type(raw: str) -> Optional[PokemonType]:
    raw = raw.strip()
    for pt in PokemonType:
        if pt.value.lower() == raw.lower():
            return pt
    return None


def _parse_energy_cost(raw: str) -> List[PokemonType]:
    """Parse a cost string such as 'Fire Fire Colorless' into a list."""
    tokens = raw.strip().split()
    cost: List[PokemonType] = []
    for token in tokens:
        pt = _parse_type(token)
        if pt:
            cost.append(pt)
        elif token.strip():
            # Unknown token – treat as Colorless
            cost.append(PokemonType.COLORLESS)
    return cost


def _parse_damage(raw: str) -> int:
    """Extract the numeric damage value from strings like '120' or '60+'."""
    cleaned = raw.strip().replace("+", "").replace("×", "").replace("x", "")
    try:
        return int(cleaned)
    except ValueError:
        return 0


def _parse_hp(raw: str) -> Optional[int]:
    try:
        return int(raw.strip())
    except ValueError:
        return None


def _parse_retreat(raw: str) -> int:
    try:
        return int(raw.strip())
    except ValueError:
        return 0


def _parse_card_category(raw: str) -> CardCategory:
    raw = raw.strip().lower()
    if "trainer" in raw:
        return CardCategory.TRAINER
    if "energy" in raw:
        return CardCategory.ENERGY
    return CardCategory.POKEMON


def _parse_trainer_subtype(raw: str) -> Optional[TrainerSubtype]:
    raw = raw.strip().lower()
    if "supporter" in raw:
        return TrainerSubtype.SUPPORTER
    if "item" in raw:
        return TrainerSubtype.ITEM
    if "stadium" in raw:
        return TrainerSubtype.STADIUM
    return None


def _parse_energy_subtype(raw: str) -> EnergySubtype:
    if "special" in raw.strip().lower():
        return EnergySubtype.SPECIAL
    return EnergySubtype.BASIC


# ---------------------------------------------------------------------------
# CSV loader
# ---------------------------------------------------------------------------


def load_cards_from_csv(filepath: str | Path) -> List[Card]:
    """
    Load card records from the competition CSV file.

    The CSV schema expected::

        Card ID, Card Name, Expansion, Collection No.,
        Stage (Pokémon) / Type (Energy and Trainer), Rule, Category,
        Previous stage, HP, Type, Weakness, Resistance (Type), Retreat,
        Move Name, Cost, Damage, Effect Explanation

    Multiple moves per card are represented as additional rows with the
    same Card ID.

    Parameters
    ----------
    filepath:
        Path to the EN Card Data.csv or JP Card Data.csv file.

    Returns
    -------
    List[Card]
        Deduplicated list of Card objects, one per unique Card ID.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"Card data file not found: {filepath}")

    cards_by_id: Dict[str, Card] = {}

    with open(filepath, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            row = {k.strip(): v.strip() for k, v in row.items() if k}
            card_id = row.get("Card ID", "").strip()
            if not card_id:
                continue

            if card_id not in cards_by_id:
                category_str = row.get("Category", "")
                category = _parse_card_category(category_str)

                stage_field = row.get("Stage (Pokémon) / Type (Energy and Trainer)", "")

                card = Card(
                    card_id=card_id,
                    card_name=row.get("Card Name", ""),
                    expansion=row.get("Expansion", ""),
                    collection_no=row.get("Collection No.", ""),
                    category=category,
                    rule_text=row.get("Rule", ""),
                )

                if category == CardCategory.POKEMON:
                    card.stage = stage_field.strip() or None
                    card.previous_stage = row.get("Previous stage", "").strip() or None
                    card.hp = _parse_hp(row.get("HP", ""))
                    card.pokemon_type = _parse_type(row.get("Type", ""))
                    card.weakness = _parse_type(row.get("Weakness", ""))
                    card.resistance = _parse_type(row.get("Resistance (Type)", ""))
                    card.retreat_cost = _parse_retreat(row.get("Retreat", "0"))

                elif category == CardCategory.TRAINER:
                    card.trainer_subtype = _parse_trainer_subtype(stage_field)

                elif category == CardCategory.ENERGY:
                    card.energy_subtype = _parse_energy_subtype(stage_field)
                    card.energy_type = _parse_type(row.get("Type", ""))

                cards_by_id[card_id] = card

            # Append move if present
            move_name = row.get("Move Name", "").strip()
            if move_name and card_id in cards_by_id:
                move = Move(
                    name=move_name,
                    cost=_parse_energy_cost(row.get("Cost", "")),
                    damage=_parse_damage(row.get("Damage", "0")),
                    effect=row.get("Effect Explanation", ""),
                )
                cards_by_id[card_id].moves.append(move)

    return list(cards_by_id.values())


# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------


class CardAnalyzer:
    """
    Provides aggregate analysis and filtering over a loaded card pool.

    Parameters
    ----------
    cards:
        List of Card objects (output of :func:`load_cards_from_csv`).
    """

    def __init__(self, cards: List[Card]) -> None:
        self.cards = cards
        self._build_indices()

    # ------------------------------------------------------------------
    # Index building
    # ------------------------------------------------------------------

    def _build_indices(self) -> None:
        self._by_id: Dict[str, Card] = {c.card_id: c for c in self.cards}
        self._by_category: Dict[CardCategory, List[Card]] = defaultdict(list)
        self._by_type: Dict[Optional[PokemonType], List[Card]] = defaultdict(list)
        self._by_expansion: Dict[str, List[Card]] = defaultdict(list)

        for card in self.cards:
            self._by_category[card.category].append(card)
            if card.is_pokemon:
                self._by_type[card.pokemon_type].append(card)
            self._by_expansion[card.expansion].append(card)

    # ------------------------------------------------------------------
    # Basic filters
    # ------------------------------------------------------------------

    def get_by_id(self, card_id: str) -> Optional[Card]:
        return self._by_id.get(card_id)

    def get_pokemon(self) -> List[Card]:
        return list(self._by_category[CardCategory.POKEMON])

    def get_trainers(self) -> List[Card]:
        return list(self._by_category[CardCategory.TRAINER])

    def get_energies(self) -> List[Card]:
        return list(self._by_category[CardCategory.ENERGY])

    def get_basics(self) -> List[Card]:
        return [c for c in self.get_pokemon() if c.is_basic]

    def get_by_type(self, pokemon_type: PokemonType) -> List[Card]:
        return list(self._by_type[pokemon_type])

    def get_supporters(self) -> List[Card]:
        return [
            c for c in self.get_trainers()
            if c.trainer_subtype == TrainerSubtype.SUPPORTER
        ]

    def get_items(self) -> List[Card]:
        return [
            c for c in self.get_trainers()
            if c.trainer_subtype == TrainerSubtype.ITEM
        ]

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def summary_stats(self) -> Dict[str, Any]:
        """Return a dictionary of aggregate statistics for the card pool."""
        pokemon = self.get_pokemon()
        trainers = self.get_trainers()
        energies = self.get_energies()

        hp_values = [c.hp for c in pokemon if c.hp is not None]
        retreat_values = [c.retreat_cost for c in pokemon]

        all_damages = [
            m.damage
            for c in pokemon
            for m in c.moves
            if m.damage > 0
        ]

        return {
            "total_cards": len(self.cards),
            "pokemon_count": len(pokemon),
            "trainer_count": len(trainers),
            "energy_count": len(energies),
            "basic_pokemon_count": len(self.get_basics()),
            "expansions": len(set(c.expansion for c in self.cards)),
            "avg_hp": round(sum(hp_values) / len(hp_values), 1) if hp_values else 0,
            "max_hp": max(hp_values) if hp_values else 0,
            "min_hp": min(hp_values) if hp_values else 0,
            "avg_retreat": round(sum(retreat_values) / len(retreat_values), 2)
            if retreat_values
            else 0,
            "avg_move_damage": round(sum(all_damages) / len(all_damages), 1)
            if all_damages
            else 0,
            "max_move_damage": max(all_damages) if all_damages else 0,
        }

    def top_damage_pokemon(self, n: int = 10) -> List[Tuple[Card, float]]:
        """Return the top-n Pokémon ranked by their best move's damage-per-energy."""
        scored: List[Tuple[Card, float]] = []
        for card in self.get_pokemon():
            bm = card.best_move
            if bm and bm.damage > 0:
                scored.append((card, bm.damage_per_energy))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:n]

    def low_retreat_basics(self, max_retreat: int = 1) -> List[Card]:
        """Basics with retreat cost ≤ *max_retreat* – good pivot Pokémon."""
        return [
            c for c in self.get_basics()
            if c.retreat_cost <= max_retreat
        ]

    def type_distribution(self) -> Dict[str, int]:
        """Count of Pokémon cards per type."""
        dist: Dict[str, int] = defaultdict(int)
        for card in self.get_pokemon():
            key = card.pokemon_type.value if card.pokemon_type else "Unknown"
            dist[key] += 1
        return dict(sorted(dist.items(), key=lambda x: x[1], reverse=True))

    def expansion_distribution(self) -> Dict[str, int]:
        """Count of cards per expansion set."""
        dist: Dict[str, int] = defaultdict(int)
        for card in self.cards:
            dist[card.expansion] += 1
        return dict(sorted(dist.items(), key=lambda x: x[1], reverse=True))

    def weakness_targets(self, attacking_type: PokemonType) -> List[Card]:
        """All Pokémon that are weak to *attacking_type*."""
        return [
            c for c in self.get_pokemon()
            if c.weakness == attacking_type
        ]

    def print_summary(self) -> None:
        """Print a human-readable summary to stdout."""
        stats = self.summary_stats()
        print("=" * 55)
        print("  Pokémon TCG Card Pool – Analysis Summary")
        print("=" * 55)
        for key, val in stats.items():
            print(f"  {key:<30} {val}")
        print()
        print("  Type distribution (Pokémon):")
        for ptype, count in self.type_distribution().items():
            bar = "█" * (count // 2)
            print(f"  {ptype:<15} {count:>4}  {bar}")
        print()
        print("  Top-10 Pokémon by damage/energy:")
        for rank, (card, score) in enumerate(self.top_damage_pokemon(10), 1):
            bm = card.best_move
            print(
                f"  {rank:>2}. {card.card_name:<30} "
                f"{bm.damage:>4} dmg / {bm.energy_count} nrg = {score:.1f}"
            )
        print("=" * 55)
