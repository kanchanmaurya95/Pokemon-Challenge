"""
Pokemon TCG AI Training Agent
Decision engine for automated Pokemon TCG battles.
Implements heuristic-based strategy with opening, mid-game, and late-game phases.
"""

import json
import os
import random
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class GamePhase(Enum):
    OPENING = "opening"
    MIDGAME = "midgame"
    LATEGAME = "lategame"


@dataclass
class Card:
    card_id: int
    name: str
    card_type: str  # pokemon, trainer, energy
    stage: str  # basic, stage1, stage2, energy, trainer
    hp: int = 0
    energy_type: str = ""
    retreat_cost: int = 0
    moves: list = field(default_factory=list)
    ability: Optional[str] = None
    is_ex: bool = False


@dataclass
class Move:
    name: str
    cost: int
    damage: int
    effect: str = ""


@dataclass
class GameState:
    """Represents the current state of the game visible to the agent."""
    turn: int = 0
    prizes_remaining: int = 6
    opponent_prizes_remaining: int = 6
    hand: list = field(default_factory=list)
    active_pokemon: Optional[dict] = None
    bench: list = field(default_factory=list)
    opponent_active: Optional[dict] = None
    opponent_bench_count: int = 0
    energy_attached_this_turn: bool = False
    supporter_played_this_turn: bool = False


class PokemonTCGAgent:
    """
    AI Training Agent for Pokemon TCG.
    Uses heuristic-based decision making with phase-aware strategy.
    """

    def __init__(self, deck_config_path=None):
        self.deck_config = self._load_deck_config(deck_config_path)
        self.game_log = []
        self.stats = {"wins": 0, "losses": 0, "turns_total": 0}

    def _load_deck_config(self, path):
        """Load deck configuration."""
        if path and os.path.exists(path):
            with open(path) as f:
                return json.load(f)
        return self._default_deck_config()

    def _default_deck_config(self):
        """Default aggressive Basic-ex deck configuration."""
        return {
            "name": "Basic Ex Rush",
            "strategy": "aggressive",
            "pokemon": [],
            "trainers": [],
            "energy": [],
        }

    def determine_phase(self, state: GameState) -> GamePhase:
        """Determine current game phase based on prizes and board state."""
        total_prizes_taken = (6 - state.prizes_remaining) + (6 - state.opponent_prizes_remaining)
        if state.turn <= 2 or total_prizes_taken == 0:
            return GamePhase.OPENING
        elif state.prizes_remaining <= 2 or state.opponent_prizes_remaining <= 2:
            return GamePhase.LATEGAME
        return GamePhase.MIDGAME

    def decide_action(self, state: GameState) -> dict:
        """
        Main decision function. Returns the best action given current game state.
        Called each turn by the game simulator.
        """
        phase = self.determine_phase(state)
        self.game_log.append({"turn": state.turn, "phase": phase.value})

        actions = []

        # Priority 1: Play supporters for draw/search (if not already played)
        if not state.supporter_played_this_turn:
            supporter_action = self._evaluate_supporters(state, phase)
            if supporter_action:
                actions.append(supporter_action)

        # Priority 2: Evolve Pokemon if possible
        evolve_action = self._evaluate_evolutions(state, phase)
        if evolve_action:
            actions.append(evolve_action)

        # Priority 3: Attach energy
        if not state.energy_attached_this_turn:
            energy_action = self._evaluate_energy_attachment(state, phase)
            if energy_action:
                actions.append(energy_action)

        # Priority 4: Play item cards
        item_actions = self._evaluate_items(state, phase)
        actions.extend(item_actions)

        # Priority 5: Bench Pokemon
        bench_action = self._evaluate_bench(state, phase)
        if bench_action:
            actions.append(bench_action)

        # Priority 6: Retreat decision
        retreat_action = self._evaluate_retreat(state, phase)
        if retreat_action:
            actions.append(retreat_action)

        # Priority 7: Attack (usually last action of turn)
        attack_action = self._evaluate_attack(state, phase)
        if attack_action:
            actions.append(attack_action)

        # Return highest priority action
        if actions:
            return actions[0]
        return {"action": "pass"}

    def _evaluate_supporters(self, state: GameState, phase: GamePhase) -> Optional[dict]:
        """Evaluate which supporter to play."""
        supporters = [c for c in state.hand if c.get("type") == "supporter"]
        if not supporters:
            return None

        # Prioritize draw supporters early, disruption late
        if phase == GamePhase.OPENING:
            # Prefer draw supporters
            draw_supporters = [s for s in supporters if "draw" in s.get("effect", "").lower()]
            if draw_supporters:
                return {"action": "play_supporter", "card": draw_supporters[0]}
        elif phase == GamePhase.LATEGAME:
            # Prefer boss/gust effects to close game
            gust_supporters = [s for s in supporters if "switch" in s.get("effect", "").lower()
                              or "active" in s.get("effect", "").lower()]
            if gust_supporters:
                return {"action": "play_supporter", "card": gust_supporters[0]}

        # Default: play first available supporter
        return {"action": "play_supporter", "card": supporters[0]}

    def _evaluate_evolutions(self, state: GameState, phase: GamePhase) -> Optional[dict]:
        """Evaluate if any Pokemon should evolve."""
        evolutions = [c for c in state.hand if c.get("stage") in ("stage1", "stage2")]
        if not evolutions:
            return None

        # Check if we have matching pre-evolution on bench or active
        for evo in evolutions:
            prev_stage = evo.get("previous_stage", "")
            targets = []
            if state.active_pokemon and state.active_pokemon.get("name") == prev_stage:
                targets.append("active")
            for i, bench_mon in enumerate(state.bench):
                if bench_mon.get("name") == prev_stage:
                    targets.append(f"bench_{i}")
            if targets:
                return {"action": "evolve", "card": evo, "target": targets[0]}
        return None

    def _evaluate_energy_attachment(self, state: GameState, phase: GamePhase) -> Optional[dict]:
        """Decide where to attach energy."""
        energy_cards = [c for c in state.hand if c.get("type") == "energy"]
        if not energy_cards:
            return None

        # Attach to active if it needs energy to attack
        if state.active_pokemon:
            active_energy_needed = state.active_pokemon.get("energy_needed", 0)
            if active_energy_needed > 0:
                return {"action": "attach_energy", "card": energy_cards[0], "target": "active"}

        # Otherwise attach to bench Pokemon being set up
        for i, bench_mon in enumerate(state.bench):
            if bench_mon.get("energy_needed", 0) > 0:
                return {"action": "attach_energy", "card": energy_cards[0], "target": f"bench_{i}"}

        # Default: attach to active
        if state.active_pokemon:
            return {"action": "attach_energy", "card": energy_cards[0], "target": "active"}
        return None

    def _evaluate_items(self, state: GameState, phase: GamePhase) -> list:
        """Evaluate item cards to play."""
        items = [c for c in state.hand if c.get("type") == "item"]
        actions = []
        for item in items:
            # Play draw items (e.g., Pokeball variants for search)
            if any(kw in item.get("effect", "").lower()
                   for kw in ["draw", "search", "deck", "hand"]):
                actions.append({"action": "play_item", "card": item})
        return actions

    def _evaluate_bench(self, state: GameState, phase: GamePhase) -> Optional[dict]:
        """Decide whether to bench Pokemon."""
        basic_pokemon = [c for c in state.hand
                        if c.get("type") == "pokemon" and c.get("stage") == "basic"]
        if not basic_pokemon or len(state.bench) >= 5:
            return None

        # In opening, bench setup Pokemon and backup attackers
        if phase == GamePhase.OPENING:
            # Prefer Pokemon with abilities or that evolve
            setup = [p for p in basic_pokemon if p.get("has_ability") or p.get("evolves_to")]
            if setup:
                return {"action": "bench", "card": setup[0]}
            return {"action": "bench", "card": basic_pokemon[0]}

        # In mid/late game, only bench if we need backup
        if len(state.bench) < 2:
            return {"action": "bench", "card": basic_pokemon[0]}
        return None

    def _evaluate_retreat(self, state: GameState, phase: GamePhase) -> Optional[dict]:
        """Decide whether to retreat active Pokemon."""
        if not state.active_pokemon or not state.bench:
            return None

        active = state.active_pokemon
        # Retreat if active is low HP and we have a better attacker ready
        hp_remaining = active.get("hp", 0) - active.get("damage_taken", 0)
        max_hp = active.get("hp", 100)

        if hp_remaining < max_hp * 0.3:
            # Find bench Pokemon ready to attack
            for i, bench_mon in enumerate(state.bench):
                if bench_mon.get("energy_needed", 0) == 0:
                    return {"action": "retreat", "target": f"bench_{i}"}
        return None

    def _evaluate_attack(self, state: GameState, phase: GamePhase) -> Optional[dict]:
        """Choose which attack to use."""
        if not state.active_pokemon:
            return None

        moves = state.active_pokemon.get("moves", [])
        available_moves = [m for m in moves if m.get("can_use", False)]

        if not available_moves:
            return None

        # Choose move based on phase
        if phase == GamePhase.LATEGAME:
            # Use highest damage to close game
            best = max(available_moves, key=lambda m: m.get("damage", 0))
        else:
            # Use best damage-to-effect ratio
            best = max(available_moves, key=lambda m: m.get("damage", 0))

        return {"action": "attack", "move": best}

    def choose_active_pokemon(self, state: GameState) -> Optional[dict]:
        """Choose starting active Pokemon (or replacement when KO'd)."""
        basic_pokemon = [c for c in state.hand
                        if c.get("type") == "pokemon" and c.get("stage") == "basic"]
        if not basic_pokemon:
            return None

        # Prefer: lowest retreat cost for flexibility, or highest HP for survivability
        # Score by: HP * 0.4 + (4 - retreat) * 0.3 + has_good_attack * 0.3
        def score(p):
            hp = p.get("hp", 0)
            retreat = p.get("retreat_cost", 2)
            max_dmg = max((m.get("damage", 0) for m in p.get("moves", [])), default=0)
            return hp * 0.004 + (4 - retreat) * 0.3 + (max_dmg / 100) * 0.3

        best = max(basic_pokemon, key=score)
        return {"action": "choose_active", "card": best}

    def on_game_end(self, won: bool, final_state: GameState):
        """Record game result for statistics."""
        if won:
            self.stats["wins"] += 1
        else:
            self.stats["losses"] += 1
        self.stats["turns_total"] += final_state.turn

    def get_win_rate(self) -> float:
        """Get current win rate."""
        total = self.stats["wins"] + self.stats["losses"]
        return self.stats["wins"] / total if total > 0 else 0.0

    def get_stats(self) -> dict:
        """Get agent statistics."""
        total = self.stats["wins"] + self.stats["losses"]
        return {
            "total_games": total,
            "wins": self.stats["wins"],
            "losses": self.stats["losses"],
            "win_rate": self.get_win_rate(),
            "avg_turns": self.stats["turns_total"] / total if total > 0 else 0,
        }
