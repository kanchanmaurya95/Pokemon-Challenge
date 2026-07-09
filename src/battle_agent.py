"""
AI Battle Agent for the Pokémon TCG AI Battle Challenge.

Architecture
------------
The agent uses a **greedy heuristic search** strategy: at each decision
point it scores all legal actions and picks the highest-scoring one.

Action priority (highest → lowest):
1. **Attack to knock out** – if an attack can KO the opponent's active
   Pokémon this turn, prefer it (captures prize card).
2. **Attack for weakness** – amplify damage by targeting type weaknesses.
3. **Attach energy** – move towards being able to attack sooner.
4. **Play Supporter** – draw/search to improve hand quality.
5. **Play Item** – search / recovery items improve board state.
6. **Bench Pokémon** – guarantee at least one backup attacker.
7. **Retreat** – switch to a healthier / more threatening Pokémon.
8. **Pass** – do nothing (last resort).

The heuristic scoring function incorporates:
* HP advantage (our HP remaining vs. opponent HP remaining).
* Prize card differential (fewer prizes remaining for us = closer to win).
* Bench depth (wider bench = more options).
* Energy acceleration (attached energy relative to best move cost).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Tuple

from src.game_state import (
    ActivePokemon,
    Card,
    CardCategory,
    GameState,
    Move,
    PlayerState,
    PokemonType,
    TrainerSubtype,
)


# ---------------------------------------------------------------------------
# Action definitions
# ---------------------------------------------------------------------------


class ActionType(Enum):
    ATTACK = auto()
    ATTACH_ENERGY = auto()
    PLAY_SUPPORTER = auto()
    PLAY_ITEM = auto()
    BENCH_POKEMON = auto()
    RETREAT = auto()
    PASS = auto()


@dataclass
class Action:
    """A single action the agent may take during its turn."""

    action_type: ActionType
    description: str = ""
    # Optional payloads depending on action type
    card: Optional[Card] = None
    move: Optional[Move] = None
    target: Optional[ActivePokemon] = None
    bench_index: Optional[int] = None
    score: float = 0.0

    def __repr__(self) -> str:
        return f"Action({self.action_type.name}, score={self.score:.2f}: {self.description})"


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class BattleAgent:
    """
    Greedy heuristic battle agent.

    Parameters
    ----------
    verbose:
        When True, print a log of each chosen action to stdout.
    random_seed:
        Optional seed for reproducible random tie-breaking.
    """

    def __init__(self, verbose: bool = False, random_seed: Optional[int] = None) -> None:
        self.verbose = verbose
        if random_seed is not None:
            random.seed(random_seed)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def choose_action(self, state: GameState) -> Action:
        """
        Choose the best action given the current *state*.

        Parameters
        ----------
        state:
            The current full game state from the agent's perspective.

        Returns
        -------
        Action
            The highest-scoring legal action.
        """
        actions = self._generate_actions(state)
        if not actions:
            return Action(ActionType.PASS, description="No legal actions available.")

        scored = [self._score_action(action, state) for action in actions]
        best = max(scored, key=lambda a: a.score)

        if self.verbose:
            print(f"[Turn {state.turn_number}] Agent chooses: {best}")

        return best

    def play_turn(self, state: GameState) -> List[Action]:
        """
        Execute a full turn, returning the ordered list of actions taken.

        The agent keeps acting until it has:
        * Attached one energy (mandatory per-turn action),
        * Played available Supporters / Items, and
        * Attacked (ends the turn) or passed.
        """
        actions_taken: List[Action] = []
        energy_attached = False
        supporter_played = False
        attacked = False

        for _ in range(20):  # Safety cap to prevent infinite loops
            if attacked:
                break

            player = state.player
            hand_pokemon = [c for c in player.hand if c.is_pokemon]
            hand_energy = [c for c in player.hand if c.is_energy]
            hand_supporters = [
                c for c in player.hand
                if c.is_trainer and c.trainer_subtype == TrainerSubtype.SUPPORTER
            ]
            hand_items = [
                c for c in player.hand
                if c.is_trainer and c.trainer_subtype == TrainerSubtype.ITEM
            ]

            action = self.choose_action(state)

            if action.action_type == ActionType.PASS:
                actions_taken.append(action)
                break
            if action.action_type == ActionType.ATTACK:
                actions_taken.append(action)
                attacked = True
                break
            if action.action_type == ActionType.ATTACH_ENERGY:
                if not energy_attached:
                    actions_taken.append(action)
                    energy_attached = True
                    # Actually perform attachment in state
                    if action.card and player.active:
                        energy_type = action.card.energy_type or PokemonType.COLORLESS
                        player.active.attach_energy(energy_type)
                        player.hand.remove(action.card)
                else:
                    # Already attached – skip to other actions
                    break
            elif action.action_type == ActionType.PLAY_SUPPORTER:
                if not supporter_played and not player.supporter_played_this_turn:
                    actions_taken.append(action)
                    supporter_played = True
                    player.supporter_played_this_turn = True
                    if action.card and action.card in player.hand:
                        player.hand.remove(action.card)
                    # Simulate drawing 2 cards as a generic supporter effect
                    player.draw(2)
                else:
                    break
            elif action.action_type == ActionType.BENCH_POKEMON:
                if player.bench_count < 5 and action.card:
                    actions_taken.append(action)
                    if action.card in player.hand:
                        player.hand.remove(action.card)
                    player.bench.append(ActivePokemon(card=action.card))
                else:
                    break
            elif action.action_type == ActionType.PLAY_ITEM:
                actions_taken.append(action)
                if action.card and action.card in player.hand:
                    player.hand.remove(action.card)
                # Simulate search/draw effect
                player.draw(1)
            elif action.action_type == ActionType.RETREAT:
                actions_taken.append(action)
                if player.active and action.bench_index is not None:
                    new_active = player.bench.pop(action.bench_index)
                    old_active = player.active
                    player.bench.append(old_active)
                    player.active = new_active
                break
            else:
                actions_taken.append(action)
                break

        if not attacked:
            # If we did not attack, try one final attack
            attack_action = self._best_attack(state)
            if attack_action:
                actions_taken.append(attack_action)

        return actions_taken

    # ------------------------------------------------------------------
    # Action generation
    # ------------------------------------------------------------------

    def _generate_actions(self, state: GameState) -> List[Action]:
        actions: List[Action] = []
        player = state.player
        opponent = state.opponent

        # Attack actions
        if player.active and opponent.active:
            for move in player.active.card.moves:
                if player.active.can_use_move(move):
                    actions.append(
                        Action(
                            ActionType.ATTACK,
                            description=f"Use {move.name} ({move.damage} dmg)",
                            move=move,
                            target=opponent.active,
                        )
                    )

        # Attach energy
        energy_in_hand = [c for c in player.hand if c.is_energy]
        if energy_in_hand and player.active:
            actions.append(
                Action(
                    ActionType.ATTACH_ENERGY,
                    description=f"Attach {energy_in_hand[0].card_name}",
                    card=energy_in_hand[0],
                    target=player.active,
                )
            )

        # Bench Pokémon
        basic_in_hand = [c for c in player.hand if c.is_pokemon and c.is_basic]
        if basic_in_hand and player.bench_count < 5:
            actions.append(
                Action(
                    ActionType.BENCH_POKEMON,
                    description=f"Bench {basic_in_hand[0].card_name}",
                    card=basic_in_hand[0],
                )
            )

        # Play Supporter
        if not player.supporter_played_this_turn:
            supporters_in_hand = [
                c for c in player.hand
                if c.is_trainer and c.trainer_subtype == TrainerSubtype.SUPPORTER
            ]
            if supporters_in_hand:
                actions.append(
                    Action(
                        ActionType.PLAY_SUPPORTER,
                        description=f"Play {supporters_in_hand[0].card_name}",
                        card=supporters_in_hand[0],
                    )
                )

        # Play Item
        items_in_hand = [
            c for c in player.hand
            if c.is_trainer and c.trainer_subtype == TrainerSubtype.ITEM
        ]
        if items_in_hand:
            actions.append(
                Action(
                    ActionType.PLAY_ITEM,
                    description=f"Play {items_in_hand[0].card_name}",
                    card=items_in_hand[0],
                )
            )

        # Retreat
        if player.active and player.bench:
            for i, bench_mon in enumerate(player.bench):
                if (
                    player.active.card.retreat_cost
                    <= player.active.total_energy
                ):
                    actions.append(
                        Action(
                            ActionType.RETREAT,
                            description=(
                                f"Retreat to {bench_mon.card.card_name}"
                            ),
                            target=bench_mon,
                            bench_index=i,
                        )
                    )

        if not actions:
            actions.append(Action(ActionType.PASS, description="Pass turn"))

        return actions

    def _best_attack(self, state: GameState) -> Optional[Action]:
        """Return the highest-scoring attack action, or None."""
        player = state.player
        opponent = state.opponent
        if not player.active or not opponent.active:
            return None
        attack_actions = [
            Action(
                ActionType.ATTACK,
                description=f"Use {move.name} ({move.damage} dmg)",
                move=move,
                target=opponent.active,
            )
            for move in player.active.card.moves
            if player.active.can_use_move(move)
        ]
        if not attack_actions:
            return None
        scored = [self._score_action(a, state) for a in attack_actions]
        return max(scored, key=lambda a: a.score)

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _score_action(self, action: Action, state: GameState) -> Action:
        """Assign a heuristic score to *action* and return it."""
        score = 0.0
        player = state.player
        opponent = state.opponent

        if action.action_type == ActionType.ATTACK and action.move and action.target:
            move = action.move
            target = action.target

            # Apply weakness/resistance
            damage = move.damage
            if (
                target.card.weakness
                and player.active
                and player.active.card.pokemon_type == target.card.weakness
            ):
                damage *= 2
            if (
                target.card.resistance
                and player.active
                and player.active.card.pokemon_type == target.card.resistance
            ):
                damage = max(0, damage - 30)

            # Strongly prefer knock-outs
            if damage >= target.current_hp:
                score += 1000.0
            else:
                # Partial damage – proportional credit
                hp = target.card.hp or 1
                score += 500.0 * (damage / hp)

            # Efficiency bonus
            score += move.damage_per_energy * 10

            # Prefer targeting 2-prize Pokémon (rule box Pokémon)
            if "V" in target.card.card_name or "ex" in target.card.card_name.lower():
                score += 200.0

        elif action.action_type == ActionType.ATTACH_ENERGY:
            # Prioritise if active Pokémon still needs energy to attack
            if player.active and player.active.card.best_move:
                needed = player.active.card.best_move.energy_count
                current = player.active.total_energy
                score = 300.0 - (current / max(needed, 1)) * 100
            else:
                score = 100.0

        elif action.action_type == ActionType.PLAY_SUPPORTER:
            # Draw/search is very high value, especially early
            score = 250.0 + max(0, 5 - state.turn_number) * 20

        elif action.action_type == ActionType.BENCH_POKEMON:
            # Benching is important early; less so once bench is full
            score = 200.0 - (player.bench_count * 30)

        elif action.action_type == ActionType.PLAY_ITEM:
            score = 150.0

        elif action.action_type == ActionType.RETREAT:
            # Retreat only if active is close to KO and bench is healthier
            if player.active and action.target:
                active_hp_pct = player.active.current_hp / max(player.active.card.hp or 1, 1)
                bench_hp_pct = action.target.current_hp / max(action.target.card.hp or 1, 1)
                if active_hp_pct < 0.25 and bench_hp_pct > 0.5:
                    score = 180.0
                else:
                    score = 50.0
            else:
                score = 50.0

        elif action.action_type == ActionType.PASS:
            score = -100.0

        # Global board-state adjustments
        my_prizes = player.prizes_remaining
        opp_prizes = opponent.prizes_remaining
        score += (6 - my_prizes) * 15  # we're closer to winning
        score -= (6 - opp_prizes) * 10  # opponent is closer to winning

        action.score = score
        return action

    # ------------------------------------------------------------------
    # Evaluation / simulation
    # ------------------------------------------------------------------

    def evaluate_state(self, state: GameState) -> float:
        """
        Return a scalar evaluation of the game state from the agent's
        perspective.  Positive values indicate an advantage.
        """
        player = state.player
        opponent = state.opponent

        score = 0.0

        # Prize card differential (lower remaining prizes = better)
        score += (6 - player.prizes_remaining) * 100
        score -= (6 - opponent.prizes_remaining) * 100

        # HP advantage on active Pokémon
        if player.active:
            score += player.active.current_hp * 0.5
        if opponent.active:
            score -= opponent.active.current_hp * 0.5

        # Bench depth
        score += player.bench_count * 20
        score -= opponent.bench_count * 15

        # Energy readiness of active
        if player.active and player.active.card.best_move:
            needed = player.active.card.best_move.energy_count
            attached = player.active.total_energy
            readiness = min(1.0, attached / max(needed, 1))
            score += readiness * 50

        # Hand size advantage
        score += len(player.hand) * 5
        score -= len(opponent.hand) * 3

        return score
