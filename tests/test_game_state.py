"""
Tests for the game state module.

These tests verify core data structures: cards, moves, active Pokémon,
player state, and the full game-state container.
"""

import pytest

from src.game_state import (
    ActivePokemon,
    Card,
    CardCategory,
    EnergySubtype,
    GameState,
    Move,
    PlayerState,
    PokemonType,
    TrainerSubtype,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_fire_basic(card_id: str = "F001", hp: int = 120) -> Card:
    card = Card(
        card_id=card_id,
        card_name="Charizard EX",
        expansion="SET-A",
        collection_no="001",
        category=CardCategory.POKEMON,
        stage="Basic",
        hp=hp,
        pokemon_type=PokemonType.FIRE,
        weakness=PokemonType.WATER,
        retreat_cost=2,
    )
    card.moves = [
        Move(
            name="Flamethrower",
            cost=[PokemonType.FIRE, PokemonType.FIRE, PokemonType.COLORLESS],
            damage=120,
            effect="Discard an energy.",
        ),
        Move(
            name="Ember",
            cost=[PokemonType.FIRE],
            damage=30,
        ),
    ]
    return card


def make_water_basic(card_id: str = "W001", hp: int = 100) -> Card:
    card = Card(
        card_id=card_id,
        card_name="Blastoise EX",
        expansion="SET-A",
        collection_no="002",
        category=CardCategory.POKEMON,
        stage="Basic",
        hp=hp,
        pokemon_type=PokemonType.WATER,
        weakness=PokemonType.LIGHTNING,
        retreat_cost=1,
    )
    card.moves = [
        Move(
            name="Hydro Pump",
            cost=[PokemonType.WATER, PokemonType.WATER],
            damage=80,
        ),
    ]
    return card


def make_supporter() -> Card:
    return Card(
        card_id="S001",
        card_name="Professor's Research",
        expansion="SET-A",
        collection_no="100",
        category=CardCategory.TRAINER,
        trainer_subtype=TrainerSubtype.SUPPORTER,
    )


def make_fire_energy() -> Card:
    return Card(
        card_id="E001",
        card_name="Fire Energy",
        expansion="BASE",
        collection_no="E1",
        category=CardCategory.ENERGY,
        energy_subtype=EnergySubtype.BASIC,
        energy_type=PokemonType.FIRE,
    )


# ---------------------------------------------------------------------------
# Move tests
# ---------------------------------------------------------------------------


class TestMove:
    def test_energy_count(self):
        move = Move(
            name="Flamethrower",
            cost=[PokemonType.FIRE, PokemonType.FIRE, PokemonType.COLORLESS],
            damage=120,
        )
        assert move.energy_count == 3

    def test_damage_per_energy(self):
        move = Move(
            name="Ember",
            cost=[PokemonType.FIRE],
            damage=30,
        )
        assert move.damage_per_energy == pytest.approx(30.0)

    def test_damage_per_energy_zero_cost(self):
        move = Move(name="Free", cost=[], damage=20)
        assert move.damage_per_energy == pytest.approx(20.0)

    def test_zero_damage_move(self):
        move = Move(name="Noop", cost=[PokemonType.COLORLESS], damage=0)
        assert move.damage_per_energy == 0.0


# ---------------------------------------------------------------------------
# Card tests
# ---------------------------------------------------------------------------


class TestCard:
    def test_is_basic(self):
        card = make_fire_basic()
        assert card.is_basic
        assert card.is_pokemon
        assert not card.is_trainer
        assert not card.is_energy

    def test_best_move_selects_highest_efficiency(self):
        card = make_fire_basic()
        # Ember: 30/1=30, Flamethrower: 120/3=40 – Flamethrower wins
        assert card.best_move is not None
        assert card.best_move.name == "Flamethrower"

    def test_best_move_none_when_no_moves(self):
        card = Card(
            card_id="X1",
            card_name="No-move",
            expansion="X",
            collection_no="0",
            category=CardCategory.POKEMON,
        )
        assert card.best_move is None

    def test_repr(self):
        card = make_fire_basic()
        assert "F001" in repr(card)


# ---------------------------------------------------------------------------
# ActivePokemon tests
# ---------------------------------------------------------------------------


class TestActivePokemon:
    def test_initial_hp(self):
        card = make_fire_basic(hp=120)
        active = ActivePokemon(card=card)
        assert active.current_hp == 120

    def test_apply_damage(self):
        card = make_fire_basic(hp=120)
        active = ActivePokemon(card=card)
        dealt = active.apply_damage(50)
        assert dealt == 50
        assert active.current_hp == 70

    def test_weakness_doubles_damage(self):
        # Fire Pokémon weak to Water; attacking with Water type
        card = make_fire_basic(hp=120)
        active = ActivePokemon(card=card)
        dealt = active.apply_damage(60, attacking_type=PokemonType.WATER)
        assert dealt == 120
        assert active.current_hp == 0

    def test_resistance_reduces_damage(self):
        card = Card(
            card_id="T1",
            card_name="Togekiss",
            expansion="X",
            collection_no="1",
            category=CardCategory.POKEMON,
            hp=150,
            resistance=PokemonType.FIGHTING,
        )
        active = ActivePokemon(card=card)
        dealt = active.apply_damage(60, attacking_type=PokemonType.FIGHTING)
        assert dealt == 30
        assert active.current_hp == 120

    def test_is_knocked_out_when_hp_zero(self):
        card = make_fire_basic(hp=60)
        active = ActivePokemon(card=card)
        active.apply_damage(60)
        assert active.is_knocked_out

    def test_can_use_move_sufficient_energy(self):
        card = make_fire_basic()
        active = ActivePokemon(card=card)
        active.attach_energy(PokemonType.FIRE)
        ember = card.moves[1]  # cost: [Fire]
        assert active.can_use_move(ember)

    def test_cannot_use_move_insufficient_energy(self):
        card = make_fire_basic()
        active = ActivePokemon(card=card)
        flamethrower = card.moves[0]  # cost: [Fire, Fire, Colorless]
        assert not active.can_use_move(flamethrower)

    def test_can_use_colorless_move_with_any_energy(self):
        card = make_fire_basic()
        active = ActivePokemon(card=card)
        move = Move(name="Slash", cost=[PokemonType.COLORLESS], damage=30)
        card.moves.append(move)
        active.attach_energy(PokemonType.WATER)  # any type satisfies Colorless
        assert active.can_use_move(move)

    def test_attach_energy_accumulates(self):
        card = make_fire_basic()
        active = ActivePokemon(card=card)
        active.attach_energy(PokemonType.FIRE)
        active.attach_energy(PokemonType.FIRE)
        assert active.attached_energy[PokemonType.FIRE] == 2
        assert active.total_energy == 2


# ---------------------------------------------------------------------------
# PlayerState tests
# ---------------------------------------------------------------------------


class TestPlayerState:
    def _make_player_with_deck(self, size: int = 10) -> PlayerState:
        ps = PlayerState()
        for i in range(size):
            ps.deck.append(make_fire_basic(card_id=f"F{i:03d}"))
        return ps

    def test_draw_removes_from_deck(self):
        ps = self._make_player_with_deck(10)
        drawn = ps.draw(3)
        assert len(drawn) == 3
        assert len(ps.deck) == 7
        assert len(ps.hand) == 3

    def test_draw_does_not_exceed_deck(self):
        ps = self._make_player_with_deck(2)
        drawn = ps.draw(5)
        assert len(drawn) == 2
        assert len(ps.deck) == 0

    def test_setup_prize_cards(self):
        ps = self._make_player_with_deck(10)
        ps.setup_prize_cards(6)
        assert len(ps.prize_cards) == 6
        assert len(ps.deck) == 4

    def test_take_prize_adds_to_hand(self):
        ps = self._make_player_with_deck(10)
        ps.setup_prize_cards(6)
        card = ps.take_prize()
        assert card in ps.hand
        assert len(ps.prize_cards) == 5

    def test_has_lost_when_no_pokemon(self):
        ps = PlayerState()
        # No active, no bench, no deck, no hand
        assert ps.has_lost

    def test_all_in_play(self):
        card = make_fire_basic()
        ps = PlayerState()
        ps.active = ActivePokemon(card=card)
        ps.bench.append(ActivePokemon(card=make_water_basic()))
        assert len(ps.all_in_play) == 2


# ---------------------------------------------------------------------------
# GameState tests
# ---------------------------------------------------------------------------


class TestGameState:
    def test_end_turn_switches_player(self):
        gs = GameState()
        assert gs.current_player_is_me
        gs.end_turn()
        assert not gs.current_player_is_me

    def test_turn_increments_every_full_round(self):
        gs = GameState()
        assert gs.turn_number == 1
        gs.end_turn()  # opponent's turn
        assert gs.turn_number == 1
        gs.end_turn()  # back to us → turn 2
        assert gs.turn_number == 2

    def test_is_game_over_when_player_has_no_pokemon(self):
        gs = GameState()
        # Player has no Pokémon in play and no cards
        assert gs.is_game_over()

    def test_winner_returns_opponent_when_player_loses(self):
        gs = GameState()
        gs.opponent.active = ActivePokemon(card=make_water_basic())
        gs.opponent.deck = [make_water_basic()]
        # Both sides need prize cards so the "0 prizes = won" path does not
        # fire prematurely.  The player still has prizes to take, so they
        # have not won by prize collection.
        gs.opponent.prize_cards = [make_water_basic(card_id="WP01")]
        gs.player.prize_cards = [make_fire_basic(card_id="PP01")]
        # player has no Pokémon and no deck → player loses → opponent wins
        assert gs.winner() == "opponent"
