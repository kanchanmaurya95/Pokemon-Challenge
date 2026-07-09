"""
Tests for the battle agent module.
"""

import pytest

from src.battle_agent import Action, ActionType, BattleAgent
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
# Card factory helpers
# ---------------------------------------------------------------------------


def _pokemon(card_id, name, hp, ptype=PokemonType.FIRE, stage="Basic",
             retreat=1, weakness=None, resistance=None, moves=None):
    card = Card(
        card_id=card_id,
        card_name=name,
        expansion="TEST",
        collection_no=card_id,
        category=CardCategory.POKEMON,
        stage=stage,
        hp=hp,
        pokemon_type=ptype,
        weakness=weakness,
        resistance=resistance,
        retreat_cost=retreat,
    )
    card.moves = moves or []
    return card


def _energy_card(card_id="E001", etype=PokemonType.FIRE):
    return Card(
        card_id=card_id,
        card_name=f"{etype.value} Energy",
        expansion="BASE",
        collection_no=card_id,
        category=CardCategory.ENERGY,
        energy_subtype=EnergySubtype.BASIC,
        energy_type=etype,
    )


def _supporter(card_id="S001", name="Professor's Research"):
    return Card(
        card_id=card_id,
        card_name=name,
        expansion="TEST",
        collection_no=card_id,
        category=CardCategory.TRAINER,
        trainer_subtype=TrainerSubtype.SUPPORTER,
    )


def _item(card_id="I001", name="Ultra Ball"):
    return Card(
        card_id=card_id,
        card_name=name,
        expansion="TEST",
        collection_no=card_id,
        category=CardCategory.TRAINER,
        trainer_subtype=TrainerSubtype.ITEM,
    )


# ---------------------------------------------------------------------------
# Shared game state builders
# ---------------------------------------------------------------------------


def _basic_game_state(
    player_hp=120,
    opp_hp=80,
    player_energy_attached=0,
    player_prizes=6,
    opp_prizes=6,
) -> GameState:
    """Build a minimal game state with one active Pokémon per side."""
    fire_move = Move("Flamethrower", [PokemonType.FIRE, PokemonType.COLORLESS], 90)
    ember = Move("Ember", [PokemonType.FIRE], 30)

    player_card = _pokemon("P001", "Charizard", player_hp, PokemonType.FIRE,
                           moves=[fire_move, ember])
    opp_card = _pokemon("O001", "Blastoise", opp_hp, PokemonType.WATER,
                        weakness=PokemonType.LIGHTNING)

    player_active = ActivePokemon(card=player_card)
    for _ in range(player_energy_attached):
        player_active.attach_energy(PokemonType.FIRE)

    opp_active = ActivePokemon(card=opp_card)

    player_state = PlayerState()
    player_state.active = player_active
    player_state.prize_cards = [
        _pokemon(f"PZ{i}", f"Prize{i}", 60) for i in range(player_prizes)
    ]
    player_state.deck = [_pokemon(f"D{i}", f"Filler{i}", 60) for i in range(10)]

    opp_state = PlayerState()
    opp_state.active = opp_active
    opp_state.prize_cards = [
        _pokemon(f"OZ{i}", f"OPrize{i}", 60) for i in range(opp_prizes)
    ]

    return GameState(player=player_state, opponent=opp_state)


# ---------------------------------------------------------------------------
# BattleAgent.choose_action tests
# ---------------------------------------------------------------------------


class TestChooseAction:
    def test_returns_action_object(self):
        agent = BattleAgent(random_seed=42)
        state = _basic_game_state(player_energy_attached=2)
        action = agent.choose_action(state)
        assert isinstance(action, Action)

    def test_prefers_ko_attack(self):
        """With enough energy, a KO attack should be chosen."""
        agent = BattleAgent(random_seed=42)
        # Opponent has 30 HP; Ember does 30 dmg with 1 Fire energy
        state = _basic_game_state(opp_hp=30, player_energy_attached=1)
        action = agent.choose_action(state)
        assert action.action_type == ActionType.ATTACK

    def test_attaches_energy_when_available_in_hand(self):
        """Without enough energy to attack, attaching energy is preferred."""
        agent = BattleAgent(random_seed=42)
        state = _basic_game_state(player_energy_attached=0)
        # Give player a fire energy in hand
        state.player.hand = [_energy_card()]
        action = agent.choose_action(state)
        assert action.action_type == ActionType.ATTACH_ENERGY

    def test_plays_supporter_early(self):
        """Supporters should be played early for card advantage."""
        agent = BattleAgent(random_seed=42)
        state = _basic_game_state(player_energy_attached=0)
        state.turn_number = 1
        state.player.hand = [_supporter()]
        action = agent.choose_action(state)
        assert action.action_type in (ActionType.PLAY_SUPPORTER, ActionType.ATTACH_ENERGY)

    def test_passes_when_no_legal_actions(self):
        """With an empty hand, no energy, and no moves ready, agent should PASS."""
        agent = BattleAgent(random_seed=42)
        state = _basic_game_state(player_energy_attached=0)
        state.player.hand = []
        # Remove all moves from active card
        state.player.active.card.moves = []
        action = agent.choose_action(state)
        assert action.action_type == ActionType.PASS

    def test_benches_basic_pokemon(self):
        """Agent should bench a Basic Pokémon when bench is empty and hand has one."""
        agent = BattleAgent(random_seed=42)
        state = _basic_game_state(player_energy_attached=0)
        state.player.active.card.moves = []  # No attacks
        state.player.hand = [_pokemon("B001", "Bencher", 60)]
        action = agent.choose_action(state)
        assert action.action_type == ActionType.BENCH_POKEMON


# ---------------------------------------------------------------------------
# BattleAgent.evaluate_state tests
# ---------------------------------------------------------------------------


class TestEvaluateState:
    def test_leading_prize_advantage_is_positive(self):
        """If we have fewer prizes remaining, our score should be higher."""
        agent = BattleAgent()
        state_ahead = _basic_game_state(player_prizes=3, opp_prizes=6)
        state_behind = _basic_game_state(player_prizes=6, opp_prizes=3)
        assert agent.evaluate_state(state_ahead) > agent.evaluate_state(state_behind)

    def test_evaluate_returns_float(self):
        agent = BattleAgent()
        state = _basic_game_state()
        score = agent.evaluate_state(state)
        assert isinstance(score, float)

    def test_more_bench_pokemon_is_better(self):
        agent = BattleAgent()
        state_small = _basic_game_state()
        state_wide = _basic_game_state()
        # Add 3 bench Pokémon to the wide-bench state
        for i in range(3):
            state_wide.player.bench.append(
                ActivePokemon(card=_pokemon(f"BEN{i}", f"Bench{i}", 80))
            )
        assert agent.evaluate_state(state_wide) > agent.evaluate_state(state_small)


# ---------------------------------------------------------------------------
# BattleAgent.play_turn tests
# ---------------------------------------------------------------------------


class TestPlayTurn:
    def test_play_turn_returns_list_of_actions(self):
        agent = BattleAgent(random_seed=1)
        state = _basic_game_state(player_energy_attached=2)
        actions = agent.play_turn(state)
        assert isinstance(actions, list)
        assert all(isinstance(a, Action) for a in actions)

    def test_play_turn_at_most_one_energy_attached(self):
        """A player can attach at most one energy per turn."""
        agent = BattleAgent(random_seed=1)
        state = _basic_game_state(player_energy_attached=0)
        state.player.hand = [_energy_card(), _energy_card("E002")]
        actions = agent.play_turn(state)
        attach_count = sum(1 for a in actions if a.action_type == ActionType.ATTACH_ENERGY)
        assert attach_count <= 1

    def test_play_turn_at_most_one_supporter(self):
        """A player can play at most one Supporter per turn."""
        agent = BattleAgent(random_seed=1)
        state = _basic_game_state(player_energy_attached=0)
        state.player.hand = [_supporter("S001"), _supporter("S002")]
        actions = agent.play_turn(state)
        supporter_count = sum(1 for a in actions if a.action_type == ActionType.PLAY_SUPPORTER)
        assert supporter_count <= 1

    def test_play_turn_attacks_when_possible(self):
        """Agent should include an attack in the turn when energy is ready."""
        agent = BattleAgent(random_seed=1)
        state = _basic_game_state(player_energy_attached=2)
        actions = agent.play_turn(state)
        action_types = {a.action_type for a in actions}
        assert ActionType.ATTACK in action_types
