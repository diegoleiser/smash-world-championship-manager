"""Tests for frozen-strength Live Group forecasts."""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import tournament_manager as tournament  # noqa: E402
from monte_carlo.config import load_model_config  # noqa: E402
from monte_carlo.day_performance import estimate_group_day  # noqa: E402
from monte_carlo.group_simulation import SimulationPlayer  # noqa: E402
from monte_carlo.live_group import (  # noqa: E402
    LOSERS_LOCKED,
    SIDE_OPEN,
    WINNERS_LOCKED,
    LiveGroupMatch,
    forecast_live_group,
)
from monte_carlo.model import CombinedModel, PlayerParameters  # noqa: E402
from monte_carlo.live_service import (  # noqa: E402
    LiveDraftGroupState,
    forecast_live_draft_bracket,
    forecast_live_draft_group,
    load_live_draft_group_states,
)
from tournament.group_stage_standings import (  # noqa: E402
    GROUP_MATCH_CANCELLED,
    GROUP_MATCH_COMPLETED,
    GROUP_MATCH_FORFEIT,
    GROUP_MATCH_PENDING,
)


class LiveGroupForecastTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_model_config(
            PROJECT_ROOT / "config" / "model_freeze_candidate_v0.2.json"
        )
        self.players = [
            SimulationPlayer(
                player_id=player_id,
                display_name=player_id.upper(),
                initial_seed=seed,
                initial_elo=1100.0 - seed * 10,
            )
            for seed, player_id in enumerate(["a", "b", "c", "d"], start=1)
        ]
        parameters = {
            player.player_id: PlayerParameters(
                player.player_id,
                player.display_name,
                0.5 - player.initial_seed * 0.2,
            )
            for player in self.players
        }
        self.model = CombinedModel(self.config, parameters, {})
        self.matches = [
            LiveGroupMatch(
                "a",
                "b",
                GROUP_MATCH_COMPLETED,
                "a",
                2,
                1,
            ),
            LiveGroupMatch(
                "a",
                "c",
                GROUP_MATCH_FORFEIT,
                "c",
            ),
            LiveGroupMatch("a", "d", GROUP_MATCH_CANCELLED),
            LiveGroupMatch("b", "c", GROUP_MATCH_PENDING),
            LiveGroupMatch("b", "d", GROUP_MATCH_PENDING),
            LiveGroupMatch("c", "d", GROUP_MATCH_PENDING),
        ]

    def test_completed_results_are_fixed_and_pending_sets_are_forecast(
        self,
    ) -> None:
        forecast = forecast_live_group(
            self.players,
            self.matches,
            self.model,
            n_simulations=200,
            random_seed=17,
            winners_count=2,
        )
        by_player = {
            player.player_id: player for player in forecast.players
        }
        self.assertEqual(
            (
                by_player["a"].current_sets_won,
                by_player["a"].current_sets_lost,
            ),
            (1, 1),
        )
        self.assertEqual(
            (
                by_player["c"].current_sets_won,
                by_player["c"].current_sets_lost,
            ),
            (1, 0),
        )
        self.assertEqual(forecast.completed_sets, 2)
        self.assertEqual(forecast.pending_sets, 3)
        self.assertEqual(len(forecast.match_leverage), 3)
        for player in forecast.players:
            self.assertAlmostEqual(
                sum(player.group_seed_probabilities.values()),
                1.0,
            )
            self.assertIn(
                player.winners_status,
                {WINNERS_LOCKED, SIDE_OPEN, LOSERS_LOCKED},
            )
        for match in forecast.match_leverage:
            for probability in (
                match.player_1_set_win_probability,
                match.player_1_winners_if_win,
                match.player_1_winners_if_loss,
                match.player_2_winners_if_win,
                match.player_2_winners_if_loss,
            ):
                self.assertGreaterEqual(probability, 0.0)
                self.assertLessEqual(probability, 1.0)
        self.assertAlmostEqual(
            sum(player.winners_probability for player in forecast.players),
            2.0,
        )

    def test_day_sigma_does_not_affect_remaining_group_forecast(self) -> None:
        no_day_model = CombinedModel(
            replace(self.config, sigma_day=0.0),
            self.model.players,
            self.model.h2h_effects,
        )
        large_day_model = CombinedModel(
            replace(self.config, sigma_day=5.0),
            self.model.players,
            self.model.h2h_effects,
        )
        first = forecast_live_group(
            self.players,
            self.matches,
            no_day_model,
            100,
            99,
            winners_count=2,
        )
        second = forecast_live_group(
            self.players,
            self.matches,
            large_day_model,
            100,
            99,
            winners_count=2,
        )
        self.assertEqual(first.players, second.players)

    def test_complete_group_has_deterministic_final_probabilities(self) -> None:
        complete_matches = [
            LiveGroupMatch(
                match.player_1_id,
                match.player_2_id,
                (
                    GROUP_MATCH_COMPLETED
                    if match.status == GROUP_MATCH_PENDING
                    else match.status
                ),
                (
                    match.player_1_id
                    if match.status == GROUP_MATCH_PENDING
                    else match.winner_id
                ),
                2 if match.status == GROUP_MATCH_PENDING else match.player_1_score,
                0 if match.status == GROUP_MATCH_PENDING else match.player_2_score,
            )
            for match in self.matches
        ]
        forecast = forecast_live_group(
            self.players,
            complete_matches,
            self.model,
            20,
            5,
            winners_count=2,
        )
        self.assertEqual(forecast.pending_sets, 0)
        self.assertEqual(forecast.match_leverage, ())
        status_by_player = {
            player.player_id: player.winners_status
            for player in forecast.players
        }
        self.assertEqual(status_by_player["b"], WINNERS_LOCKED)
        self.assertEqual(status_by_player["c"], WINNERS_LOCKED)
        self.assertEqual(status_by_player["a"], LOSERS_LOCKED)
        self.assertEqual(status_by_player["d"], LOSERS_LOCKED)
        for player in forecast.players:
            probabilities = set(player.group_seed_probabilities.values())
            self.assertLessEqual(probabilities, {0.0, 1.0})

    def test_complete_tied_group_uses_final_tiebreak_for_locked_status(self) -> None:
        tied_matches = [
            LiveGroupMatch(
                "a",
                "b",
                GROUP_MATCH_COMPLETED,
                "a",
                2,
                0,
            ),
            LiveGroupMatch(
                "b",
                "c",
                GROUP_MATCH_COMPLETED,
                "b",
                2,
                0,
            ),
            LiveGroupMatch(
                "c",
                "a",
                GROUP_MATCH_COMPLETED,
                "c",
                2,
                1,
            ),
        ]
        forecast = forecast_live_group(
            self.players[:3],
            tied_matches,
            self.model,
            20,
            5,
            winners_count=1,
        )
        status_by_player = {
            player.player_id: player.winners_status
            for player in forecast.players
        }
        self.assertEqual(status_by_player["a"], WINNERS_LOCKED)
        self.assertEqual(status_by_player["b"], LOSERS_LOCKED)
        self.assertEqual(status_by_player["c"], LOSERS_LOCKED)
        self.assertNotIn(SIDE_OPEN, status_by_player.values())

    def test_late_lock_uses_head_to_head_at_winners_boundary(self) -> None:
        players = [
            SimulationPlayer(
                player_id=player_id,
                display_name=player_id.upper(),
                initial_seed=seed,
                initial_elo=1100.0 - seed * 10,
            )
            for seed, player_id in enumerate(
                ["a", "b", "c", "d", "e", "f"],
                start=1,
            )
        ]
        model = CombinedModel(
            self.config,
            {
                player.player_id: PlayerParameters(
                    player.player_id,
                    player.display_name,
                    0.5 - player.initial_seed * 0.2,
                )
                for player in players
            },
            {},
        )
        winners = {
            ("a", "b"): "a",
            ("a", "c"): "a",
            ("a", "d"): "d",
            ("a", "e"): "a",
            ("b", "c"): "b",
            ("b", "d"): "b",
            ("b", "e"): "e",
            ("c", "d"): "c",
            ("c", "e"): "c",
            ("d", "e"): "d",
            ("a", "f"): "a",
            ("b", "f"): "b",
            ("c", "f"): "c",
            ("e", "f"): "e",
        }
        matches = [
            LiveGroupMatch(
                player_1_id=player_1_id,
                player_2_id=player_2_id,
                status=GROUP_MATCH_COMPLETED,
                winner_id=winner_id,
                player_1_score=2 if winner_id == player_1_id else 1,
                player_2_score=2 if winner_id == player_2_id else 1,
            )
            for (player_1_id, player_2_id), winner_id in winners.items()
        ]
        matches.append(
            LiveGroupMatch("d", "f", GROUP_MATCH_PENDING)
        )

        forecast = forecast_live_group(
            players,
            matches,
            model,
            n_simulations=20,
            random_seed=7,
            winners_count=4,
        )
        status_by_player = {
            player.player_id: player.winners_status
            for player in forecast.players
        }

        self.assertEqual(status_by_player["d"], WINNERS_LOCKED)
        self.assertEqual(status_by_player["e"], LOSERS_LOCKED)

    def test_draft_service_derives_winners_count_from_bracket_size(self) -> None:
        state = LiveDraftGroupState(
            draft_id="draft",
            tournament_number=99,
            group_id="group",
            group_name="Group 1",
            players=tuple(self.players),
            matches=tuple(self.matches),
        )
        with patch(
            "monte_carlo.live_service.load_live_draft_group_states",
            return_value=(state,),
        ):
            forecast = forecast_live_draft_group(
                "unused.db",
                "draft",
                self.model,
                20,
                1,
            )
        self.assertAlmostEqual(
            sum(
                player.winners_probability
                for player in forecast.players
            ),
            2.0,
        )


class DayPosteriorTests(unittest.TestCase):
    def setUp(self) -> None:
        config = load_model_config(
            PROJECT_ROOT / "config" / "model_freeze_candidate_v0.2.json"
        )
        self.player_ids = ["a", "b", "c"]
        self.model = CombinedModel(
            config,
            {
                player_id: PlayerParameters(
                    player_id,
                    player_id.upper(),
                    0.0,
                    0.0,
                )
                for player_id in self.player_ids
            },
            {},
        )
        self.complete_matches = [
            LiveGroupMatch(
                "a",
                "b",
                GROUP_MATCH_COMPLETED,
                "a",
                2,
                0,
            ),
            LiveGroupMatch(
                "a",
                "c",
                GROUP_MATCH_COMPLETED,
                "a",
                2,
                0,
            ),
            LiveGroupMatch(
                "b",
                "c",
                GROUP_MATCH_COMPLETED,
                "b",
                2,
                1,
            ),
        ]

    def test_complete_group_estimates_and_centers_day_values(self) -> None:
        estimate = estimate_group_day(
            self.player_ids,
            self.complete_matches,
            self.model,
        )
        self.assertTrue(estimate.success)
        self.assertEqual(estimate.completed_score_sets, 3)
        self.assertGreater(estimate.values["a"], estimate.values["b"])
        self.assertGreater(estimate.values["b"], estimate.values["c"])
        self.assertAlmostEqual(sum(estimate.values.values()), 0.0, places=8)

    def test_pending_set_blocks_day_activation(self) -> None:
        with self.assertRaisesRegex(ValueError, "only after"):
            estimate_group_day(
                self.player_ids,
                [
                    *self.complete_matches,
                    LiveGroupMatch("a", "c", GROUP_MATCH_PENDING),
                ],
                self.model,
            )

    def test_forfeit_does_not_create_day_evidence(self) -> None:
        estimate = estimate_group_day(
            self.player_ids,
            [
                self.complete_matches[0],
                LiveGroupMatch(
                    "a",
                    "c",
                    GROUP_MATCH_FORFEIT,
                    "a",
                ),
            ],
            self.model,
        )
        self.assertEqual(estimate.completed_score_sets, 1)


class LiveDraftBracketForecastTests(unittest.TestCase):
    """Forecast a generated bracket after a real single-group draft."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temporary_directory.name) / "draft.db"
        with closing(sqlite3.connect(self.db_path)) as connection, connection:
            for sql_path in (
                SRC_DIR / "schema.sql",
                *sorted((SRC_DIR / "migrations").glob("*.sql")),
            ):
                connection.executescript(sql_path.read_text())
        config = load_model_config(
            PROJECT_ROOT / "config" / "model_freeze_candidate_v0.2.json"
        )
        self.model = CombinedModel(
            config,
            {
                f"p{seed}": PlayerParameters(
                    f"p{seed}",
                    f"Player {seed}",
                    0.0,
                )
                for seed in range(1, 8)
            },
            {},
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def create_group_draft(
        self,
        participant_count: int,
        *,
        leave_pending: int = 0,
    ) -> str:
        with closing(sqlite3.connect(self.db_path)) as connection, connection:
            connection.executemany(
                """
                INSERT OR IGNORE INTO players (player_id, display_name)
                VALUES (?, ?)
                """,
                [
                    (f"p{seed}", f"Player {seed}")
                    for seed in range(1, participant_count + 1)
                ],
            )
        draft_id = tournament.create_draft(
            self.db_path,
            tournament_number=99,
            tournament_date="2026-10-10",
            format_type=tournament.FORMAT_GROUP_STAGE,
            bracket_entry_mode=tournament.ENTRY_SPLIT_BY_GROUP_SEED,
        )
        for seed in range(1, participant_count + 1):
            tournament.add_participant(
                self.db_path,
                draft_id,
                f"p{seed}",
                manual_seed=seed,
            )
        tournament.create_draft_groups(self.db_path, draft_id, 1)
        tournament.create_draft_group_matches(self.db_path, draft_id)
        group_matches = tournament.get_draft_group_matches(
            self.db_path,
            draft_id,
        )
        for match in group_matches[leave_pending:]:
            tournament.update_draft_group_match(
                self.db_path,
                str(match["group_match_id"]),
                status=GROUP_MATCH_COMPLETED,
                player_1_score=2,
                player_2_score=0,
            )
        return draft_id

    def test_complete_group_uses_group_day_for_bracket_forecast(
        self,
    ) -> None:
        draft_id = self.create_group_draft(7)
        tournament.generate_draft_bracket(self.db_path, draft_id)
        forecast = forecast_live_draft_bracket(
            self.db_path,
            draft_id,
            self.model,
            100,
            77,
        )

        self.assertEqual(len(forecast.players), 7)
        self.assertEqual(
            {match.match_code for match in forecast.ready_matches},
            {"W1M1", "W1M2", "L1M2"},
        )
        group_state = load_live_draft_group_states(
            self.db_path,
            draft_id,
        )[0]
        day_posterior = estimate_group_day(
            [player.player_id for player in group_state.players],
            group_state.matches,
            self.model,
        )
        self.assertEqual(day_posterior.completed_score_sets, 21)
        self.assertTrue(any(day_posterior.values.values()))
        for match in forecast.ready_matches:
            self.assertAlmostEqual(
                match.player_1_win_probability,
                self.model.set_probability(
                    match.player_1_id,
                    match.player_2_id,
                    best_of=3,
                    day_a=day_posterior.values[match.player_1_id],
                    day_b=day_posterior.values[match.player_2_id],
                ),
            )
        self.assertAlmostEqual(
            sum(player.title_probability for player in forecast.players),
            1.0,
        )
        self.assertAlmostEqual(
            sum(
                player.grand_final_probability
                for player in forecast.players
            ),
            2.0,
        )
        for player in forecast.players:
            self.assertAlmostEqual(
                sum(player.placement_probabilities.values()),
                1.0,
            )

    def test_pending_group_blocks_bracket_forecast(self) -> None:
        draft_id = self.create_group_draft(7, leave_pending=1)
        with self.assertRaises(ValueError):
            tournament.generate_draft_bracket(self.db_path, draft_id)
        with self.assertRaisesRegex(ValueError, "Generate the Bracket"):
            forecast_live_draft_bracket(
                self.db_path,
                draft_id,
                self.model,
                10,
                1,
            )

    def test_five_player_bracket_forecast_handles_byes(self) -> None:
        draft_id = self.create_group_draft(5)
        tournament.generate_draft_bracket(self.db_path, draft_id)
        forecast = forecast_live_draft_bracket(
            self.db_path,
            draft_id,
            self.model,
            20,
            42,
        )
        self.assertEqual(len(forecast.players), 5)
        self.assertAlmostEqual(
            sum(player.title_probability for player in forecast.players),
            1.0,
        )
        with closing(sqlite3.connect(self.db_path)) as connection:
            winners_entries = connection.execute(
                """
                SELECT COUNT(DISTINCT player_id)
                FROM (
                    SELECT player_1_id AS player_id
                    FROM tournament_draft_bracket_matches
                    WHERE draft_id = ? AND match_code LIKE 'W1M%'
                    UNION
                    SELECT player_2_id
                    FROM tournament_draft_bracket_matches
                    WHERE draft_id = ? AND match_code LIKE 'W1M%'
                )
                WHERE player_id IS NOT NULL
                """,
                (draft_id, draft_id),
            ).fetchone()[0]
        self.assertEqual(winners_entries, 4)


if __name__ == "__main__":
    unittest.main()
