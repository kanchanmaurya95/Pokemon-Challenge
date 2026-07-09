"""
Deck builder for the Pokémon TCG AI Battle Challenge.

This module implements the deck construction strategy used by the
competition agent.  The chosen approach is a **speed-aggressive**
archetype that aims to:

1. Start attacking on turn 1 or turn 2 using high-efficiency Basic Pokémon.
2. Apply consistent pressure by targeting opponent weaknesses.
3. Maintain hand advantage through Supporter cards.
4. Close out games quickly via two-prize knock-outs.

Deck rules
----------
* Exactly 60 cards per deck.
* Maximum 4 copies of any single card (except Basic Energy).
* Must contain at least one Basic Pokémon to begin the game.
"""

from __future__ import annotations

from collections import Counter
from typing import Dict, List, Optional, Tuple

from src.card_analyzer import CardAnalyzer
from src.game_state import (
    Card,
    CardCategory,
    EnergySubtype,
    PokemonType,
    TrainerSubtype,
)

DECK_SIZE = 60
MAX_COPIES = 4
MIN_BASICS = 1

# Target card counts in a balanced aggressive deck
_POKEMON_TARGET = 18
_TRAINER_TARGET = 28
_ENERGY_TARGET = 14

# How many of each role we want
_SUPPORTER_COUNT = 8
_ITEM_COUNT = 16
_STADIUM_COUNT = 4


class DeckValidationError(Exception):
    """Raised when a deck fails validation."""


# ---------------------------------------------------------------------------
# Deck building logic
# ---------------------------------------------------------------------------


class DeckBuilder:
    """
    Constructs an optimised deck from the available card pool.

    Parameters
    ----------
    analyzer:
        A :class:`CardAnalyzer` loaded with the full competition card pool.
    preferred_type:
        Primary Pokémon type for the deck (e.g. ``PokemonType.FIRE``).
        If ``None``, the builder auto-selects the most efficient type.
    """

    def __init__(
        self,
        analyzer: CardAnalyzer,
        preferred_type: Optional[PokemonType] = None,
    ) -> None:
        self.analyzer = analyzer
        self.preferred_type = preferred_type or self._select_best_type()

    # ------------------------------------------------------------------
    # Type selection
    # ------------------------------------------------------------------

    def _select_best_type(self) -> PokemonType:
        """
        Choose the Pokémon type with the highest average damage-per-energy
        across its top-5 Basic cards.
        """
        scores: Dict[PokemonType, float] = {}
        for ptype in PokemonType:
            basics = [
                c for c in self.analyzer.get_basics()
                if c.pokemon_type == ptype and c.best_move and c.best_move.damage > 0
            ]
            if not basics:
                continue
            top5 = sorted(
                basics,
                key=lambda c: c.best_move.damage_per_energy,  # type: ignore[union-attr]
                reverse=True,
            )[:5]
            scores[ptype] = sum(
                c.best_move.damage_per_energy  # type: ignore[union-attr]
                for c in top5
            ) / len(top5)
        if not scores:
            return PokemonType.COLORLESS
        return max(scores, key=lambda t: scores[t])

    # ------------------------------------------------------------------
    # Card selection helpers
    # ------------------------------------------------------------------

    def _pick_pokemon(self) -> List[Tuple[Card, int]]:
        """
        Select Pokémon cards and copy counts for the deck.

        Strategy:
        * Prioritise Basics of the preferred type with best damage/energy.
        * Include 1–2 high-damage evolved Pokémon as secondary attackers.
        * Add 1–2 low-retreat Colorless Basics as pivots/utilities.
        """
        selections: List[Tuple[Card, int]] = []
        total = 0

        # --- Main attackers: Basics of preferred type ---
        type_basics = sorted(
            [
                c for c in self.analyzer.get_basics()
                if c.pokemon_type == self.preferred_type
                and c.best_move
                and c.best_move.damage > 0
            ],
            key=lambda c: c.best_move.damage_per_energy,  # type: ignore[union-attr]
            reverse=True,
        )
        # Top attacker at 4 copies, second at 3, third at 2
        for i, card in enumerate(type_basics[:3]):
            copies = MAX_COPIES - i
            selections.append((card, copies))
            total += copies
            if total >= _POKEMON_TARGET - 4:
                break

        # --- Tech / pivot: Low-retreat Basics (Colorless) ---
        pivots = [
            c for c in self.analyzer.low_retreat_basics(max_retreat=0)
            if c.pokemon_type == PokemonType.COLORLESS
            and c not in [s[0] for s in selections]
        ][:2]
        for card in pivots:
            copies = 2
            selections.append((card, copies))
            total += copies

        # Pad with remaining type basics if we're short
        for card in type_basics[3:]:
            if total >= _POKEMON_TARGET:
                break
            copies = min(2, _POKEMON_TARGET - total)
            selections.append((card, copies))
            total += copies

        return selections

    def _pick_trainers(self) -> List[Tuple[Card, int]]:
        """
        Select Trainer cards (Supporters, Items, Stadiums).

        Priority:
        * Supporters that draw cards (Professor's Research, Marnie, etc.)
        * Search Items (Ultra Ball, Quick Ball) to find Pokémon
        * Recovery Items
        * Stadium for energy acceleration or disruption
        """
        selections: List[Tuple[Card, int]] = []
        total = 0

        # Supporters
        supporters = self.analyzer.get_supporters()
        for i, card in enumerate(supporters):
            if total >= _SUPPORTER_COUNT:
                break
            copies = min(MAX_COPIES, _SUPPORTER_COUNT - total)
            selections.append((card, copies))
            total += copies

        # Items
        items = self.analyzer.get_items()
        item_total = 0
        for card in items:
            if item_total >= _ITEM_COUNT:
                break
            copies = min(MAX_COPIES, _ITEM_COUNT - item_total)
            selections.append((card, copies))
            item_total += copies
        total += item_total

        # Stadiums
        stadiums = [
            c for c in self.analyzer.get_trainers()
            if c.trainer_subtype == TrainerSubtype.STADIUM
        ]
        stadium_total = 0
        for card in stadiums:
            if stadium_total >= _STADIUM_COUNT:
                break
            copies = min(MAX_COPIES, _STADIUM_COUNT - stadium_total)
            selections.append((card, copies))
            stadium_total += copies

        return selections

    def _pick_energy(self, pokemon_selections: List[Tuple[Card, int]]) -> List[Tuple[Card, int]]:
        """Select Basic Energy cards matching the preferred type."""
        selections: List[Tuple[Card, int]] = []
        energies = self.analyzer.get_energies()

        # Prefer basic energy of the main type
        main_energy = [
            e for e in energies
            if e.energy_subtype == EnergySubtype.BASIC
            and e.energy_type == self.preferred_type
        ]
        if main_energy:
            selections.append((main_energy[0], _ENERGY_TARGET))

        # Fallback: any basic energy
        if not selections:
            basic_energies = [
                e for e in energies
                if e.energy_subtype == EnergySubtype.BASIC
            ]
            if basic_energies:
                selections.append((basic_energies[0], _ENERGY_TARGET))

        return selections

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def build(self) -> "Deck":
        """
        Assemble and return a validated 60-card Deck.

        Raises
        ------
        DeckValidationError
            If the resulting deck cannot reach exactly 60 cards with the
            available card pool.
        """
        pokemon_picks = self._pick_pokemon()
        trainer_picks = self._pick_trainers()
        energy_picks = self._pick_energy(pokemon_picks)

        all_picks = pokemon_picks + trainer_picks + energy_picks

        # Build flat card list respecting the 60-card / 4-copy rules
        card_list: List[Card] = []
        for card, count in all_picks:
            card_list.extend([card] * count)

        # Trim or pad to exactly 60 cards
        card_list = card_list[:DECK_SIZE]
        if len(card_list) < DECK_SIZE:
            # Pad with energy cards
            extra_energy = [
                e for e in self.analyzer.get_energies()
                if e.energy_subtype == EnergySubtype.BASIC
            ]
            idx = 0
            while len(card_list) < DECK_SIZE and extra_energy:
                card_list.append(extra_energy[idx % len(extra_energy)])
                idx += 1

        deck = Deck(card_list)
        deck.validate()
        return deck

    def explain(self) -> str:
        """Return a human-readable explanation of the deck strategy."""
        lines = [
            f"Deck Strategy: Speed Aggressive ({self.preferred_type.value} type)",
            "-" * 55,
            "Goal: Attack on turn 1/2 with high damage-per-energy Basics.",
            "      Target opponent weaknesses for two-prize knock-outs.",
            "      Maintain hand advantage with Supporters.",
            "",
            f"Primary type: {self.preferred_type.value}",
        ]
        type_basics = [
            c for c in self.analyzer.get_basics()
            if c.pokemon_type == self.preferred_type
            and c.best_move
            and c.best_move.damage > 0
        ]
        if type_basics:
            best = sorted(
                type_basics,
                key=lambda c: c.best_move.damage_per_energy,  # type: ignore[union-attr]
                reverse=True,
            )[0]
            bm = best.best_move
            lines.append(
                f"Lead attacker: {best.card_name} "
                f"({bm.damage} dmg / {bm.energy_count} nrg = "  # type: ignore[union-attr]
                f"{bm.damage_per_energy:.1f} eff)"  # type: ignore[union-attr]
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Deck class
# ---------------------------------------------------------------------------


class Deck:
    """
    A validated 60-card Pokémon TCG deck.

    Parameters
    ----------
    cards:
        Flat list of 60 Card objects (with duplicates for multi-copies).
    """

    def __init__(self, cards: List[Card]) -> None:
        self.cards: List[Card] = list(cards)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> None:
        """
        Validate deck legality.

        Raises
        ------
        DeckValidationError
            On any rule violation.
        """
        if len(self.cards) != DECK_SIZE:
            raise DeckValidationError(
                f"Deck must contain exactly {DECK_SIZE} cards; "
                f"got {len(self.cards)}."
            )

        basics = [c for c in self.cards if c.is_pokemon and c.is_basic]
        if len(basics) < MIN_BASICS:
            raise DeckValidationError(
                f"Deck must contain at least {MIN_BASICS} Basic Pokémon."
            )

        counts = Counter(c.card_id for c in self.cards)
        for card_id, count in counts.items():
            # Basic energy cards may exceed 4 copies
            card = next(c for c in self.cards if c.card_id == card_id)
            is_basic_energy = (
                card.category == CardCategory.ENERGY
                and card.energy_subtype == EnergySubtype.BASIC
            )
            if not is_basic_energy and count > MAX_COPIES:
                raise DeckValidationError(
                    f"Card '{card_id}' appears {count} times "
                    f"(max {MAX_COPIES})."
                )

    # ------------------------------------------------------------------
    # Composition summary
    # ------------------------------------------------------------------

    def composition(self) -> Dict[str, int]:
        """Return counts by broad category."""
        result: Dict[str, int] = {"Pokémon": 0, "Trainer": 0, "Energy": 0}
        for card in self.cards:
            result[card.category.value] += 1
        return result

    def card_counts(self) -> Dict[str, int]:
        """Return {card_name: count} mapping."""
        counts: Dict[str, int] = Counter()
        for card in self.cards:
            counts[card.card_name] += 1  # type: ignore[assignment]
        return dict(sorted(counts.items()))

    def __len__(self) -> int:
        return len(self.cards)

    def __repr__(self) -> str:
        comp = self.composition()
        return (
            f"Deck(Pokémon={comp['Pokémon']}, "
            f"Trainer={comp['Trainer']}, "
            f"Energy={comp['Energy']})"
        )
