"""
Tests for the deck builder module.
"""

import pytest

from src.card_analyzer import CardAnalyzer
from src.deck_builder import Deck, DeckBuilder, DeckValidationError, DECK_SIZE
from src.game_state import (
    Card,
    CardCategory,
    EnergySubtype,
    Move,
    PokemonType,
    TrainerSubtype,
)


# ---------------------------------------------------------------------------
# Card factory helpers
# ---------------------------------------------------------------------------


def _make_pokemon(card_id, name, ptype, hp=100, stage="Basic", retreat=1, moves=None):
    card = Card(
        card_id=card_id,
        card_name=name,
        expansion="TEST",
        collection_no=card_id,
        category=CardCategory.POKEMON,
        stage=stage,
        hp=hp,
        pokemon_type=ptype,
        retreat_cost=retreat,
    )
    card.moves = moves or [
        Move("Attack", [ptype], 50)
    ]
    return card


def _make_trainer(card_id, name, subtype):
    return Card(
        card_id=card_id,
        card_name=name,
        expansion="TEST",
        collection_no=card_id,
        category=CardCategory.TRAINER,
        trainer_subtype=subtype,
    )


def _make_energy(card_id, name, etype):
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
# Large card pool fixture (enough to fill a 60-card deck)
# ---------------------------------------------------------------------------


@pytest.fixture
def large_card_pool():
    """A synthetic card pool large enough for deck construction."""
    cards = []

    # 10 different Fire Basics (high damage)
    for i in range(10):
        cards.append(
            _make_pokemon(
                f"F{i:03d}", f"FireMon{i}", PokemonType.FIRE, hp=100 + i * 10,
                moves=[Move("Flamethrower", [PokemonType.FIRE, PokemonType.COLORLESS], 60 + i * 5)]
            )
        )

    # 5 Colorless zero-retreat basics (pivots)
    for i in range(5):
        cards.append(
            _make_pokemon(
                f"C{i:03d}", f"Pivot{i}", PokemonType.COLORLESS, hp=60, retreat=0,
                moves=[Move("Tackle", [PokemonType.COLORLESS], 10)]
            )
        )

    # 4 Supporters
    for i in range(4):
        cards.append(_make_trainer(f"S{i:03d}", f"Supporter{i}", TrainerSubtype.SUPPORTER))

    # 8 Items
    for i in range(8):
        cards.append(_make_trainer(f"I{i:03d}", f"Item{i}", TrainerSubtype.ITEM))

    # 2 Stadiums
    for i in range(2):
        cards.append(_make_trainer(f"ST{i:03d}", f"Stadium{i}", TrainerSubtype.STADIUM))

    # Fire Energy
    cards.append(_make_energy("E001", "Fire Energy", PokemonType.FIRE))

    return cards


@pytest.fixture
def analyzer(large_card_pool):
    return CardAnalyzer(large_card_pool)


# ---------------------------------------------------------------------------
# DeckBuilder tests
# ---------------------------------------------------------------------------


class TestDeckBuilder:
    def test_auto_select_type_fires(self, analyzer):
        """With only Fire Pokémon having meaningful moves, Fire should be chosen."""
        builder = DeckBuilder(analyzer)
        assert builder.preferred_type == PokemonType.FIRE

    def test_manual_type_override(self, analyzer):
        builder = DeckBuilder(analyzer, preferred_type=PokemonType.COLORLESS)
        assert builder.preferred_type == PokemonType.COLORLESS

    def test_build_returns_deck(self, analyzer):
        builder = DeckBuilder(analyzer)
        deck = builder.build()
        assert isinstance(deck, Deck)

    def test_built_deck_is_60_cards(self, analyzer):
        builder = DeckBuilder(analyzer)
        deck = builder.build()
        assert len(deck) == DECK_SIZE

    def test_built_deck_has_basics(self, analyzer):
        builder = DeckBuilder(analyzer)
        deck = builder.build()
        basics = [c for c in deck.cards if c.is_pokemon and c.is_basic]
        assert len(basics) >= 1

    def test_explain_returns_string(self, analyzer):
        builder = DeckBuilder(analyzer)
        explanation = builder.explain()
        assert isinstance(explanation, str)
        assert len(explanation) > 0


# ---------------------------------------------------------------------------
# Deck validation tests
# ---------------------------------------------------------------------------


class TestDeckValidation:
    def _base_deck(self):
        """Return a list of 60 valid cards (fire basics + energy)."""
        basic = _make_pokemon("F001", "FireMon", PokemonType.FIRE)
        energy = _make_energy("E001", "Fire Energy", PokemonType.FIRE)
        # 4 copies of basic + 56 energy = 60 total
        return [basic] * 4 + [energy] * 56

    def test_valid_deck_passes(self):
        deck = Deck(self._base_deck())
        deck.validate()  # Should not raise

    def test_wrong_size_raises(self):
        cards = self._base_deck()[:59]
        with pytest.raises(DeckValidationError, match="exactly"):
            Deck(cards).validate()

    def test_too_many_copies_raises(self):
        basic = _make_pokemon("F001", "FireMon", PokemonType.FIRE)
        energy = _make_energy("E001", "Fire Energy", PokemonType.FIRE)
        # 5 copies of the same non-energy card
        cards = [basic] * 5 + [energy] * 55
        with pytest.raises(DeckValidationError, match="F001"):
            Deck(cards).validate()

    def test_basic_energy_may_exceed_four_copies(self):
        """Basic energy cards are exempt from the 4-copy rule."""
        basic = _make_pokemon("F001", "FireMon", PokemonType.FIRE)
        energy = _make_energy("E001", "Fire Energy", PokemonType.FIRE)
        # 1 Pokémon + 59 basic energy – should be legal
        cards = [basic] * 1 + [energy] * 59
        deck = Deck(cards)
        deck.validate()  # Should not raise

    def test_no_basics_raises(self):
        energy = _make_energy("E001", "Fire Energy", PokemonType.FIRE)
        # 60 basic energy cards – legal copy-count (basic energy exempt) but no Pokémon
        cards = [energy] * 60
        with pytest.raises(DeckValidationError, match="Basic"):
            Deck(cards).validate()


# ---------------------------------------------------------------------------
# Deck composition tests
# ---------------------------------------------------------------------------


class TestDeckComposition:
    def test_composition_keys(self):
        basic = _make_pokemon("F001", "FireMon", PokemonType.FIRE)
        energy = _make_energy("E001", "Fire Energy", PokemonType.FIRE)
        deck = Deck([basic] * 4 + [energy] * 56)
        comp = deck.composition()
        assert set(comp.keys()) == {"Pokémon", "Trainer", "Energy"}

    def test_composition_counts(self):
        basic = _make_pokemon("F001", "FireMon", PokemonType.FIRE)
        supporter = _make_trainer("S001", "Prof", TrainerSubtype.SUPPORTER)
        energy = _make_energy("E001", "Fire Energy", PokemonType.FIRE)
        deck = Deck([basic] * 4 + [supporter] * 4 + [energy] * 52)
        comp = deck.composition()
        assert comp["Pokémon"] == 4
        assert comp["Trainer"] == 4
        assert comp["Energy"] == 52

    def test_card_counts(self):
        basic = _make_pokemon("F001", "FireMon", PokemonType.FIRE)
        energy = _make_energy("E001", "Fire Energy", PokemonType.FIRE)
        deck = Deck([basic] * 4 + [energy] * 56)
        counts = deck.card_counts()
        assert counts["FireMon"] == 4
        assert counts["Fire Energy"] == 56

    def test_len(self):
        basic = _make_pokemon("F001", "FireMon", PokemonType.FIRE)
        energy = _make_energy("E001", "Fire Energy", PokemonType.FIRE)
        deck = Deck([basic] * 4 + [energy] * 56)
        assert len(deck) == 60

    def test_repr(self):
        basic = _make_pokemon("F001", "FireMon", PokemonType.FIRE)
        energy = _make_energy("E001", "Fire Energy", PokemonType.FIRE)
        deck = Deck([basic] * 4 + [energy] * 56)
        assert "Deck(" in repr(deck)
