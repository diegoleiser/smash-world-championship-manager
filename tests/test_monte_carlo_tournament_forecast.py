"""Tests for the title forecast that simulates groups and the bracket."""

from __future__ import annotations

import sys
import unittest
from itertools import combinations
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from monte_carlo.config import load_model_config  # noqa: E402
from monte_carlo.group_simulation import SimulationPlayer  # noqa: E402
from monte_carlo.live_group import LiveGroupMatch  # noqa: E402
from monte_carlo.live_multi_group import LiveGroupPool  # noqa: E402
from monte_carlo.model import CombinedModel, PlayerParameters  # noqa: E402
from monte_carlo.tournament_forecast import (  # noqa: E402
    forecast_group_tournament,
)
from tournament.bracket_constants import (  # noqa: E402
    ENTRY_ALL_WINNERS,
    ENTRY_SPLIT_BY_GROUP_SEED,
)
from tournament.bracket_seeding import get_bracket_size  # noqa: E402


def build_model(player_ids: list[str]) -> CombinedModel:
    config = load_model_config(
        PROJECT_ROOT / "config" / "model_freeze_candidate_v0.2.json"
    )
    return CombinedModel(
        config,
        {
            player_id: PlayerParameters(
                player_id,
                player_id.upper(),
                (len(player_ids) - index) * 0.1,
            )
            for index, player_id in enumerate(player_ids)
        },
        {},
    )


def build_groups(
    player_ids: list[str],
    group_count: int,
) -> list[LiveGroupPool]:
    """Snake-seed the players into groups with every Set still pending."""

    members: list[list[SimulationPlayer]] = [[] for _ in range(group_count)]
    for index, player_id in enumerate(player_ids):
        row, position = divmod(index, group_count)
        group_index = position if row % 2 == 0 else group_count - 1 - position
        members[group_index].append(
            SimulationPlayer(
                player_id=player_id,
                display_name=player_id.upper(),
                initial_seed=index + 1,
                initial_elo=1000.0,
            )
        )
    return [
        LiveGroupPool(
            group_id=f"g{group_index}",
            group_name=f"Group {chr(65 + group_index)}",
            players=tuple(players),
            matches=tuple(
                LiveGroupMatch(first.player_id, second.player_id, "pending")
                for first, second in combinations(players, 2)
            ),
        )
        for group_index, players in enumerate(members)
    ]


class TournamentForecastTests(unittest.TestCase):
    def assert_distributions(self, forecast, participant_count, entry_mode):
        players = forecast.players
        self.assertEqual(len(players), participant_count)
        self.assertAlmostEqual(
            sum(player.title_probability for player in players), 1.0
        )
        self.assertAlmostEqual(
            sum(player.grand_final_probability for player in players), 2.0
        )
        expected_winners = (
            get_bracket_size(participant_count) // 2
            if entry_mode == ENTRY_SPLIT_BY_GROUP_SEED
            else participant_count
        )
        self.assertAlmostEqual(
            sum(player.winners_probability for player in players),
            expected_winners,
        )

    def test_both_entry_modes_and_group_counts_keep_distributions(self) -> None:
        for entry_mode in (ENTRY_SPLIT_BY_GROUP_SEED, ENTRY_ALL_WINNERS):
            for participant_count, group_count in (
                (3, 1), (6, 1), (8, 2), (9, 3), (12, 2), (16, 4),
            ):
                with self.subTest(
                    entry_mode=entry_mode,
                    participant_count=participant_count,
                    group_count=group_count,
                ):
                    player_ids = [
                        f"p{seed}" for seed in range(1, participant_count + 1)
                    ]
                    forecast = forecast_group_tournament(
                        build_groups(player_ids, group_count),
                        entry_mode,
                        build_model(player_ids),
                        n_simulations=20,
                        random_seed=participant_count,
                    )
                    self.assert_distributions(
                        forecast, participant_count, entry_mode
                    )

    def test_same_seed_reproduces_the_forecast(self) -> None:
        player_ids = [f"p{seed}" for seed in range(1, 9)]
        groups = build_groups(player_ids, 2)
        model = build_model(player_ids)

        first = forecast_group_tournament(
            groups, ENTRY_SPLIT_BY_GROUP_SEED, model, 50, 2026
        )
        second = forecast_group_tournament(
            groups, ENTRY_SPLIT_BY_GROUP_SEED, model, 50, 2026
        )

        self.assertEqual(first, second)
        # Sorted by title chance, strongest player first.
        self.assertEqual(
            [player.title_probability for player in first.players],
            sorted(
                (player.title_probability for player in first.players),
                reverse=True,
            ),
        )

    def test_completed_group_sets_stay_fixed(self) -> None:
        player_ids = ["p1", "p2", "p3", "p4"]
        group = build_groups(player_ids, 1)[0]
        # The weakest player wins every Set; the group is decided.
        decided = LiveGroupPool(
            group_id=group.group_id,
            group_name=group.group_name,
            players=group.players,
            matches=tuple(
                LiveGroupMatch(
                    match.player_1_id,
                    match.player_2_id,
                    "completed",
                    winner_id=max(match.player_1_id, match.player_2_id),
                    player_1_score=0 if match.player_1_id < match.player_2_id else 2,
                    player_2_score=2 if match.player_1_id < match.player_2_id else 0,
                )
                for match in group.matches
            ),
        )

        forecast = forecast_group_tournament(
            [decided],
            ENTRY_SPLIT_BY_GROUP_SEED,
            build_model(player_ids),
            n_simulations=30,
            random_seed=5,
        )

        winners = {
            player.player_id: player.winners_probability
            for player in forecast.players
        }
        self.assertEqual(winners, {"p4": 1.0, "p3": 1.0, "p2": 0.0, "p1": 0.0})
        self.assertEqual(forecast.pending_group_sets, 0)
        self.assertEqual(forecast.completed_group_sets, 6)


if __name__ == "__main__":
    unittest.main()
