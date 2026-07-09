"""
Game state representation for the Pokémon Trading Card Game simulator.

This module models the core game objects used by the deck builder and
battle agent: cards, Pokémon in play, and the full board state for both
players.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class PokemonType(Enum):
    """Pokémon elemental types available in the competition card pool."""

    COLORLESS = "Colorless"
    FIRE = "Fire"
    WATER = "Water"
    GRASS = "Grass"
    LIGHTNING = "Lightning"
    PSYCHIC = "Psychic"
    FIGHTING = "Fighting"
    DARKNESS = "Darkness"
    METAL = "Metal"
    DRAGON = "Dragon"
    FAIRY = "Fairy"


class CardCategory(Enum):
    """High-level card category."""

    POKEMON = "Pokémon"
    TRAINER = "Trainer"
    ENERGY = "Energy"


class TrainerSubtype(Enum):
    """Trainer card sub-types."""

    SUPPORTER = "Supporter"
    ITEM = "Item"
    STADIUM = "Stadium"


class EnergySubtype(Enum):
    """Energy card sub-types."""

    BASIC = "Basic"
    SPECIAL = "Special"


# ---------------------------------------------------------------------------
# Card data classes
# ---------------------------------------------------------------------------


@dataclass
class Move:
    """A single attack or ability on a Pokémon card."""

    name: str
    cost: List[PokemonType]
    damage: int
    effect: str = ""

    @property
    def energy_count(self) -> int:
        """Total number of energy required regardless of type."""
        return len(self.cost)

    @property
    def damage_per_energy(self) -> float:
        """Simple efficiency metric: damage dealt per energy spent."""
        if self.energy_count == 0:
            return float(self.damage)
        return self.damage / self.energy_count


@dataclass
class Card:
    """Represents a single card as loaded from the CSV dataset."""

    card_id: str
    card_name: str
    expansion: str
    collection_no: str
    category: CardCategory

    # Pokémon-specific fields
    stage: Optional[str] = None
    previous_stage: Optional[str] = None
    hp: Optional[int] = None
    pokemon_type: Optional[PokemonType] = None
    weakness: Optional[PokemonType] = None
    resistance: Optional[PokemonType] = None
    retreat_cost: int = 0
    moves: List[Move] = field(default_factory=list)
    rule_text: str = ""

    # Trainer-specific fields
    trainer_subtype: Optional[TrainerSubtype] = None

    # Energy-specific fields
    energy_subtype: Optional[EnergySubtype] = None
    energy_type: Optional[PokemonType] = None

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def is_basic(self) -> bool:
        return self.stage == "Basic"

    @property
    def is_pokemon(self) -> bool:
        return self.category == CardCategory.POKEMON

    @property
    def is_trainer(self) -> bool:
        return self.category == CardCategory.TRAINER

    @property
    def is_energy(self) -> bool:
        return self.category == CardCategory.ENERGY

    @property
    def best_move(self) -> Optional[Move]:
        """Return the move with the highest damage-per-energy ratio."""
        if not self.moves:
            return None
        return max(self.moves, key=lambda m: m.damage_per_energy)

    def __repr__(self) -> str:
        return f"Card({self.card_id!r}, {self.card_name!r})"


# ---------------------------------------------------------------------------
# In-play Pokémon
# ---------------------------------------------------------------------------


@dataclass
class ActivePokemon:
    """A Pokémon card currently on the field with runtime battle state."""

    card: Card
    damage_counters: int = 0
    attached_energy: Dict[PokemonType, int] = field(default_factory=dict)
    status: Optional[str] = None  # "poisoned", "burned", "paralyzed", etc.

    @property
    def current_hp(self) -> int:
        hp = self.card.hp or 0
        return max(0, hp - self.damage_counters)

    @property
    def is_knocked_out(self) -> bool:
        return self.current_hp == 0

    @property
    def total_energy(self) -> int:
        return sum(self.attached_energy.values())

    def can_use_move(self, move: Move) -> bool:
        """Check whether this Pokémon has enough energy to use *move*."""
        cost_count: Dict[PokemonType, int] = {}
        colorless_needed = 0
        for energy_type in move.cost:
            if energy_type == PokemonType.COLORLESS:
                colorless_needed += 1
            else:
                cost_count[energy_type] = cost_count.get(energy_type, 0) + 1

        available = dict(self.attached_energy)
        for energy_type, needed in cost_count.items():
            if available.get(energy_type, 0) < needed:
                return False
            available[energy_type] -= needed

        # Remaining colorless can be satisfied by any energy
        remaining_energy = sum(available.values())
        return remaining_energy >= colorless_needed

    def attach_energy(self, energy_type: PokemonType) -> None:
        self.attached_energy[energy_type] = (
            self.attached_energy.get(energy_type, 0) + 1
        )

    def apply_damage(self, amount: int, attacking_type: Optional[PokemonType] = None) -> int:
        """Apply damage with weakness/resistance modifiers. Returns actual damage."""
        modified = amount
        if attacking_type and self.card.weakness == attacking_type:
            modified *= 2
        if attacking_type and self.card.resistance == attacking_type:
            modified = max(0, modified - 30)
        self.damage_counters += modified
        return modified

    def __repr__(self) -> str:
        return (
            f"ActivePokemon({self.card.card_name!r}, "
            f"HP={self.current_hp}/{self.card.hp})"
        )


# ---------------------------------------------------------------------------
# Player state
# ---------------------------------------------------------------------------


@dataclass
class PlayerState:
    """Complete game state for a single player."""

    deck: List[Card] = field(default_factory=list)
    hand: List[Card] = field(default_factory=list)
    discard: List[Card] = field(default_factory=list)
    prize_cards: List[Card] = field(default_factory=list)
    active: Optional[ActivePokemon] = None
    bench: List[ActivePokemon] = field(default_factory=list)
    supporter_played_this_turn: bool = False

    # ---- Deck / hand management ----

    def shuffle_deck(self) -> None:
        random.shuffle(self.deck)

    def draw(self, count: int = 1) -> List[Card]:
        drawn: List[Card] = []
        for _ in range(count):
            if not self.deck:
                break
            card = self.deck.pop(0)
            self.hand.append(card)
            drawn.append(card)
        return drawn

    def setup_prize_cards(self, count: int = 6) -> None:
        for _ in range(count):
            if self.deck:
                self.prize_cards.append(self.deck.pop(0))

    def take_prize(self) -> Optional[Card]:
        if self.prize_cards:
            card = self.prize_cards.pop(0)
            self.hand.append(card)
            return card
        return None

    # ---- Board queries ----

    @property
    def all_in_play(self) -> List[ActivePokemon]:
        result = []
        if self.active:
            result.append(self.active)
        result.extend(self.bench)
        return result

    @property
    def bench_count(self) -> int:
        return len(self.bench)

    @property
    def prizes_remaining(self) -> int:
        return len(self.prize_cards)

    @property
    def has_lost(self) -> bool:
        """A player loses when they have no Pokémon in play or no prize cards left (for their opponent)."""
        if self.active is None and not self.bench:
            return True
        if not self.deck and not self.hand:
            return True
        return False


# ---------------------------------------------------------------------------
# Full game state
# ---------------------------------------------------------------------------


@dataclass
class GameState:
    """Top-level container for both players and global turn information."""

    player: PlayerState = field(default_factory=PlayerState)
    opponent: PlayerState = field(default_factory=PlayerState)
    turn_number: int = 1
    current_player_is_me: bool = True

    @property
    def active_state(self) -> PlayerState:
        return self.player if self.current_player_is_me else self.opponent

    @property
    def waiting_state(self) -> PlayerState:
        return self.opponent if self.current_player_is_me else self.player

    def end_turn(self) -> None:
        self.current_player_is_me = not self.current_player_is_me
        if self.current_player_is_me:
            self.turn_number += 1
        self.active_state.supporter_played_this_turn = False

    def is_game_over(self) -> bool:
        return self.player.has_lost or self.opponent.has_lost

    def winner(self) -> Optional[str]:
        # Taking all your prize cards means you win.
        if self.player.prizes_remaining == 0:
            return "player"
        if self.opponent.prizes_remaining == 0:
            return "opponent"
        if self.player.has_lost:
            return "opponent"
        if self.opponent.has_lost:
            return "player"
        return None
