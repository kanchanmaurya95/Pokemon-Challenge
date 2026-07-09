"""
Tests for the card analyzer module.

These tests use in-memory card objects rather than the actual competition
CSV files (which are not included in the repository), so they remain
runnable without external data.
"""

import csv
import io
import textwrap
from pathlib import Path

import pytest

from src.card_analyzer import CardAnalyzer, load_cards_from_csv
from src.game_state import (
    Card,
    CardCategory,
    EnergySubtype,
    Move,
    PokemonType,
    TrainerSubtype,
)


# ---------------------------------------------------------------------------
# Helpers to create test cards
# ---------------------------------------------------------------------------


def _make_pokemon(
    card_id: str,
    name: str,
    hp: int,
    ptype: PokemonType,
    stage: str = "Basic",
    retreat: int = 1,
    weakness: PokemonType = None,
    resistance: PokemonType = None,
    moves=None,
) -> Card:
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


def _make_trainer(card_id: str, name: str, subtype: TrainerSubtype) -> Card:
    return Card(
        card_id=card_id,
        card_name=name,
        expansion="TEST",
        collection_no=card_id,
        category=CardCategory.TRAINER,
        trainer_subtype=subtype,
    )


def _make_energy(card_id: str, name: str, etype: PokemonType) -> Card:
    return Card(
        card_id=card_id,
        card_name=name,
        expansion="BASE",
        collection_no=card_id,
        category=CardCategory.ENERGY,
        energy_subtype=EnergySubtype.BASIC,
        energy_type=etype,
    )


# ---------------------------------------------------------------------------
# Shared card pool fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_cards():
    """Return a small, representative card pool for testing."""
    fire_mon = _make_pokemon(
        "F001", "Charizard EX", 200, PokemonType.FIRE,
        weakness=PokemonType.WATER, retreat=2,
        moves=[
            Move("Flamethrower", [PokemonType.FIRE, PokemonType.FIRE, PokemonType.COLORLESS], 120),
            Move("Ember", [PokemonType.FIRE], 30),
        ],
    )
    water_mon = _make_pokemon(
        "W001", "Blastoise EX", 180, PokemonType.WATER,
        weakness=PokemonType.LIGHTNING, retreat=1,
        moves=[Move("Hydro Pump", [PokemonType.WATER, PokemonType.WATER], 80)],
    )
    colorless_pivot = _make_pokemon(
        "C001", "Bidoof", 60, PokemonType.COLORLESS,
        retreat=0,
        moves=[Move("Gnaw", [PokemonType.COLORLESS], 10)],
    )
    grass_mon = _make_pokemon(
        "G001", "Venusaur EX", 170, PokemonType.GRASS,
        weakness=PokemonType.FIRE, retreat=2,
        moves=[Move("Solar Beam", [PokemonType.GRASS, PokemonType.GRASS], 100)],
    )
    supporter = _make_trainer("S001", "Professor's Research", TrainerSubtype.SUPPORTER)
    item = _make_trainer("I001", "Ultra Ball", TrainerSubtype.ITEM)
    stadium = _make_trainer("ST001", "Training Court", TrainerSubtype.STADIUM)
    fire_energy = _make_energy("E001", "Fire Energy", PokemonType.FIRE)
    water_energy = _make_energy("E002", "Water Energy", PokemonType.WATER)

    return [fire_mon, water_mon, colorless_pivot, grass_mon,
            supporter, item, stadium, fire_energy, water_energy]


@pytest.fixture
def analyzer(sample_cards):
    return CardAnalyzer(sample_cards)


# ---------------------------------------------------------------------------
# Basic filter tests
# ---------------------------------------------------------------------------


class TestCardAnalyzerFilters:
    def test_get_pokemon(self, analyzer):
        pokemon = analyzer.get_pokemon()
        assert len(pokemon) == 4
        assert all(c.is_pokemon for c in pokemon)

    def test_get_trainers(self, analyzer):
        trainers = analyzer.get_trainers()
        assert len(trainers) == 3
        assert all(c.is_trainer for c in trainers)

    def test_get_energies(self, analyzer):
        energies = analyzer.get_energies()
        assert len(energies) == 2

    def test_get_basics(self, analyzer):
        basics = analyzer.get_basics()
        assert len(basics) == 4
        assert all(c.is_basic for c in basics)

    def test_get_by_type(self, analyzer):
        fire_cards = analyzer.get_by_type(PokemonType.FIRE)
        assert len(fire_cards) == 1
        assert fire_cards[0].card_name == "Charizard EX"

    def test_get_supporters(self, analyzer):
        supporters = analyzer.get_supporters()
        assert len(supporters) == 1
        assert supporters[0].card_name == "Professor's Research"

    def test_get_items(self, analyzer):
        items = analyzer.get_items()
        assert len(items) == 1
        assert items[0].card_name == "Ultra Ball"

    def test_get_by_id(self, analyzer):
        card = analyzer.get_by_id("F001")
        assert card is not None
        assert card.card_name == "Charizard EX"

    def test_get_by_id_missing(self, analyzer):
        assert analyzer.get_by_id("NOPE") is None


# ---------------------------------------------------------------------------
# Statistics tests
# ---------------------------------------------------------------------------


class TestCardAnalyzerStats:
    def test_summary_stats_keys(self, analyzer):
        stats = analyzer.summary_stats()
        expected_keys = {
            "total_cards", "pokemon_count", "trainer_count",
            "energy_count", "basic_pokemon_count", "expansions",
            "avg_hp", "max_hp", "min_hp", "avg_retreat",
            "avg_move_damage", "max_move_damage",
        }
        assert expected_keys.issubset(stats.keys())

    def test_summary_total_count(self, analyzer, sample_cards):
        stats = analyzer.summary_stats()
        assert stats["total_cards"] == len(sample_cards)

    def test_summary_pokemon_count(self, analyzer):
        stats = analyzer.summary_stats()
        assert stats["pokemon_count"] == 4

    def test_summary_max_hp(self, analyzer):
        stats = analyzer.summary_stats()
        assert stats["max_hp"] == 200  # Charizard EX

    def test_summary_max_damage(self, analyzer):
        stats = analyzer.summary_stats()
        assert stats["max_move_damage"] == 120  # Flamethrower

    def test_type_distribution(self, analyzer):
        dist = analyzer.type_distribution()
        assert dist["Fire"] == 1
        assert dist["Water"] == 1
        assert dist["Grass"] == 1

    def test_expansion_distribution(self, analyzer):
        dist = analyzer.expansion_distribution()
        assert "TEST" in dist
        assert "BASE" in dist

    def test_top_damage_pokemon(self, analyzer):
        top = analyzer.top_damage_pokemon(n=3)
        assert len(top) <= 3
        # All returned should be Pokémon with moves
        for card, score in top:
            assert card.is_pokemon
            assert score > 0

    def test_top_damage_ranking_order(self, analyzer):
        top = analyzer.top_damage_pokemon(n=10)
        scores = [s for _, s in top]
        assert scores == sorted(scores, reverse=True)

    def test_low_retreat_basics(self, analyzer):
        zero_retreat = analyzer.low_retreat_basics(max_retreat=0)
        assert all(c.retreat_cost == 0 for c in zero_retreat)
        assert any(c.card_name == "Bidoof" for c in zero_retreat)

    def test_weakness_targets(self, analyzer):
        water_weak = analyzer.weakness_targets(PokemonType.WATER)
        assert len(water_weak) == 1
        assert water_weak[0].card_name == "Charizard EX"

    def test_weakness_targets_empty_for_unknown(self, analyzer):
        fairy_weak = analyzer.weakness_targets(PokemonType.FAIRY)
        assert fairy_weak == []


# ---------------------------------------------------------------------------
# CSV loading tests
# ---------------------------------------------------------------------------


CSV_CONTENT = textwrap.dedent("""\
    Card ID,Card Name,Expansion,Collection No.,Stage (Pokémon) / Type (Energy and Trainer),Rule,Category,Previous stage,HP,Type,Weakness,Resistance (Type),Retreat,Move Name,Cost,Damage,Effect Explanation
    P001,Pikachu,Set1,001,Basic,,Pokémon,,70,Lightning,Fighting,,1,Thunder Shock,Lightning,30,Paralyze the opponent.
    P001,Pikachu,Set1,001,Basic,,Pokémon,,70,Lightning,Fighting,,1,Thunderbolt,Lightning Lightning,90,Discard all energy.
    T001,Marnie,Set1,050,Supporter,,Trainer,,,,,,,,,, 
    E001,Lightning Energy,Base,E1,Basic,,Energy,,,,,,,,,,
""")


def test_load_cards_from_csv(tmp_path):
    csv_file = tmp_path / "test_cards.csv"
    csv_file.write_text(CSV_CONTENT, encoding="utf-8")

    cards = load_cards_from_csv(csv_file)

    # Should have 3 unique cards (P001, T001, E001)
    assert len(cards) == 3

    ids = {c.card_id for c in cards}
    assert "P001" in ids
    assert "T001" in ids
    assert "E001" in ids


def test_load_csv_pokemon_has_two_moves(tmp_path):
    csv_file = tmp_path / "test_cards.csv"
    csv_file.write_text(CSV_CONTENT, encoding="utf-8")
    cards = load_cards_from_csv(csv_file)
    pikachu = next(c for c in cards if c.card_id == "P001")
    assert len(pikachu.moves) == 2
    move_names = {m.name for m in pikachu.moves}
    assert "Thunder Shock" in move_names
    assert "Thunderbolt" in move_names


def test_load_csv_pokemon_stats(tmp_path):
    csv_file = tmp_path / "test_cards.csv"
    csv_file.write_text(CSV_CONTENT, encoding="utf-8")
    cards = load_cards_from_csv(csv_file)
    pikachu = next(c for c in cards if c.card_id == "P001")
    assert pikachu.hp == 70
    assert pikachu.pokemon_type == PokemonType.LIGHTNING
    assert pikachu.stage == "Basic"
    assert pikachu.retreat_cost == 1


def test_load_csv_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_cards_from_csv("/nonexistent/path/cards.csv")
