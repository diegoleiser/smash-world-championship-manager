"""Title forecasts for a Group Stage tournament before its bracket exists."""

from __future__ import annotations

import random
from dataclasses import dataclass

from monte_carlo.bracket_simulation import simulate_bracket
from monte_carlo.day_performance import sample_day_values
from monte_carlo.live_group import _validate_live_group, standing_match_dict
from monte_carlo.live_multi_group import LiveGroupPool
from monte_carlo.model import CombinedModel
from monte_carlo.scorelines import simulate_scoreline
from tournament.bracket_seeding import get_bracket_size
from tournament.group_stage_ranking import build_global_group_ranking
from tournament.group_stage_standings import (
    GROUP_MATCH_COMPLETED,
    GROUP_MATCH_FORFEIT,
    GROUP_MATCH_PENDING,
    calculate_group_standings,
)


@dataclass(frozen=True)
class TournamentPlayerForecast:
    player_id: str
    display_name: str
    winners_probability: float
    grand_final_probability: float
    title_probability: float


@dataclass(frozen=True)
class TournamentForecast:
    players: tuple[TournamentPlayerForecast, ...]
    bracket_entry_mode: str
    completed_group_sets: int
    pending_group_sets: int
    reset_probability: float
    simulation_count: int
    random_seed: int
    model_version: str
    training_cutoff: str
    probability_policy: str


def forecast_group_tournament(
    groups: list[LiveGroupPool],
    bracket_entry_mode: str,
    model: CombinedModel,
    n_simulations: int,
    random_seed: int,
) -> TournamentForecast:
    """Simulate the open Group Sets and the whole bracket after them.

    Each run draws one Day value per player and keeps it for the open Group
    Sets and the bracket, as for a pre-tournament simulation. Completed and
    forfeited Group Sets stay fixed. The bracket is seeded with the
    production global ranking, so group rematch avoidance and the entry mode
    match the real bracket.
    """

    if not groups:
        raise ValueError("Create tournament groups before forecasting.")
    if n_simulations < 1:
        raise ValueError("n_simulations must be positive.")
    players = [player for group in groups for player in group.players]
    player_ids = [player.player_id for player in players]
    if len(set(player_ids)) != len(player_ids):
        raise ValueError("A player cannot appear in multiple groups.")
    for group in groups:
        _validate_live_group(list(group.players), list(group.matches), model)
    get_bracket_size(len(players))

    members_by_group = {
        group.group_id: [
            {
                "player_id": player.player_id,
                "player": player.display_name,
                "initial_seed": player.initial_seed,
            }
            for player in group.players
        ]
        for group in groups
    }
    elo_by_player_id = {
        player.player_id: player.initial_elo for player in players
    }
    fixed_by_group = {
        group.group_id: [
            standing_match_dict(match)
            for match in group.matches
            if match.status != GROUP_MATCH_PENDING
        ]
        for group in groups
    }
    pending_matches = [
        (group.group_id, match)
        for group in groups
        for match in group.matches
        if match.status == GROUP_MATCH_PENDING
    ]

    winners_counts = {player_id: 0 for player_id in player_ids}
    grand_final_counts = {player_id: 0 for player_id in player_ids}
    title_counts = {player_id: 0 for player_id in player_ids}
    reset_count = 0
    rng = random.Random(random_seed)
    for _ in range(n_simulations):
        day_values = sample_day_values(
            player_ids,
            model.config.sigma_day,
            rng,
        )
        simulated_by_group = {
            group_id: list(matches)
            for group_id, matches in fixed_by_group.items()
        }
        for group_id, match in pending_matches:
            day_1 = day_values[match.player_1_id]
            day_2 = day_values[match.player_2_id]
            normal, decider = model.game_probabilities(
                match.player_1_id,
                match.player_2_id,
                day_a=day_1,
                day_b=day_2,
            )
            player_1_won = rng.random() < model.set_probability(
                match.player_1_id,
                match.player_2_id,
                best_of=3,
                day_a=day_1,
                day_b=day_2,
            )
            score = simulate_scoreline(
                player_a_won=player_1_won,
                normal_game_probability=normal,
                decider_game_probability=decider,
                best_of=3,
                rng=rng,
            )
            simulated_by_group[group_id].append(
                {
                    "player_1_id": match.player_1_id,
                    "player_2_id": match.player_2_id,
                    "status": GROUP_MATCH_COMPLETED,
                    "winner_id": (
                        match.player_1_id
                        if player_1_won
                        else match.player_2_id
                    ),
                    "player_1_score": score.player_a_score,
                    "player_2_score": score.player_b_score,
                }
            )

        ranking = build_global_group_ranking(
            [
                {
                    "group_id": group.group_id,
                    "group_name": group.group_name,
                    **calculate_group_standings(
                        members_by_group[group.group_id],
                        simulated_by_group[group.group_id],
                        elo_by_player_id,
                    ),
                }
                for group in groups
            ],
            bracket_entry_mode,
        )["ranking"]
        for row in ranking:
            if str(row["starts_in"]) == "winners":
                winners_counts[str(row["player_id"])] += 1

        bracket = simulate_bracket(
            [str(row["player_id"]) for row in ranking],
            model,
            day_values,
            rng,
            entry_mode=bracket_entry_mode,
        )
        final_set = next(
            simulated_set
            for simulated_set in reversed(bracket.sets)
            if simulated_set.match_code in {"GF", "GFR"}
        )
        for finalist in (final_set.player_1_id, final_set.player_2_id):
            grand_final_counts[finalist] += 1
        title_counts[bracket.champion_id] += 1
        if bracket.grand_final_reset_played:
            reset_count += 1

    denominator = float(n_simulations)
    forecasts = sorted(
        (
            TournamentPlayerForecast(
                player_id=player.player_id,
                display_name=player.display_name,
                winners_probability=winners_counts[player.player_id]
                / denominator,
                grand_final_probability=grand_final_counts[player.player_id]
                / denominator,
                title_probability=title_counts[player.player_id]
                / denominator,
            )
            for player in players
        ),
        key=lambda forecast: (
            -forecast.title_probability,
            -forecast.grand_final_probability,
            forecast.display_name.casefold(),
        ),
    )
    return TournamentForecast(
        players=tuple(forecasts),
        bracket_entry_mode=bracket_entry_mode,
        completed_group_sets=sum(
            match.status in {GROUP_MATCH_COMPLETED, GROUP_MATCH_FORFEIT}
            for group in groups
            for match in group.matches
        ),
        pending_group_sets=len(pending_matches),
        reset_probability=reset_count / denominator,
        simulation_count=n_simulations,
        random_seed=random_seed,
        model_version=model.config.model_version,
        training_cutoff=model.config.training_cutoff,
        probability_policy=(
            "Completed Group Sets fixed; one Day value per player and "
            "simulated tournament for the open Group Sets and the bracket; "
            "production global seeding applied."
        ),
    )
