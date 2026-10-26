"""Biggest Elo upsets: rated Set wins against a clearly higher-rated player."""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import smash_statistics as statistics  # noqa: E402
from init_db import (  # noqa: E402
    DEFAULT_MIGRATIONS_DIR,
    DEFAULT_SCHEMA_PATH,
    initialize_database,
)
from smash_stats import upsets  # noqa: E402
from smash_stats.upsets import find_upsets, get_upsets  # noqa: E402


def rated_set(
    sequence: int,
    winner: str,
    loser: str,
    winner_before: float,
    loser_before: float,
    *,
    score: tuple[int, int] | None = (2, 1),
    tournament_number: int = 1,
) -> dict:
    """One event shaped like calculate_elo_history() output."""

    return {
        "sequence": sequence,
        "match_id": f"m{sequence}",
        "tournament_id": f"wc_{tournament_number:02d}",
        "tournament_number": tournament_number,
        "tournament_date": f"2026-0{tournament_number}-01",
        "round_label": "1",
        "stage": "knockout",
        "winner_id": winner,
        "winner": winner.title(),
        "loser_id": loser,
        "loser": loser.title(),
        "winner_score": score[0] if score else None,
        "loser_score": score[1] if score else None,
        "score_known": score is not None,
        "rating_change": 20.0,
        "winner_rating_before": winner_before,
        "loser_rating_before": loser_before,
    }


def warm_up(winner: str, count: int = 5, start: int = 1) -> list[dict]:
    """Rated Sets that give a player the required history without upsets."""

    return [
        rated_set(start + index, winner, f"rookie{index}", 1000.0, 1000.0)
        for index in range(count)
    ]


class FindUpsetsTests(unittest.TestCase):
    def test_upset_fields_use_elo_before_the_set(self) -> None:
        history = warm_up("alpha") + [
            rated_set(6, "alpha", "beta", 950.25, 1110.75, score=(3, 2)),
        ]

        [upset] = find_upsets(history)

        self.assertEqual(
            {key: upset[key] for key in (
                "rank", "match_id", "winner_id", "winner", "loser_id", "loser",
                "winner_elo_before", "loser_elo_before", "elo_gap", "elo_gain",
                "winner_score", "loser_score", "score_known",
            )},
            {
                "rank": 1, "match_id": "m6", "winner_id": "alpha", "winner": "Alpha",
                "loser_id": "beta", "loser": "Beta", "winner_elo_before": 950.2,
                "loser_elo_before": 1110.8, "elo_gap": 160.5, "elo_gain": 20.0,
                "winner_score": 3, "loser_score": 2, "score_known": True,
            },
        )

    def test_favourite_wins_are_not_upsets(self) -> None:
        history = warm_up("alpha") + [rated_set(6, "alpha", "beta", 1200.0, 1000.0)]

        self.assertEqual(find_upsets(history), [])

    def test_gap_threshold_is_inclusive(self) -> None:
        history = warm_up("alpha") + [
            rated_set(6, "alpha", "beta", 1000.0, 1150.0),
            rated_set(7, "alpha", "gamma", 1000.0, 1149.99),
        ]

        self.assertEqual([upset["match_id"] for upset in find_upsets(history)], ["m6"])

    def test_winner_needs_five_rated_sets_before(self) -> None:
        upset_set = rated_set(10, "alpha", "beta", 900.0, 1100.0)

        self.assertEqual(find_upsets(warm_up("alpha", count=4) + [upset_set]), [])
        self.assertEqual(len(find_upsets(warm_up("alpha", count=5) + [upset_set])), 1)

    def test_losses_count_as_prior_sets_and_loser_history_is_irrelevant(self) -> None:
        losses = [
            rated_set(index, f"rookie{index}", "alpha", 1000.0, 1000.0)
            for index in range(1, 6)
        ]
        history = losses + [rated_set(6, "alpha", "newcomer", 900.0, 1100.0)]

        self.assertEqual(len(find_upsets(history)), 1)

    def test_biggest_gap_first_and_ties_stay_chronological(self) -> None:
        history = warm_up("alpha") + [
            rated_set(6, "alpha", "beta", 1000.0, 1150.0),
            rated_set(7, "alpha", "gamma", 1000.0, 1250.0),
            rated_set(8, "alpha", "delta", 1000.0, 1150.0),
        ]

        result = find_upsets(history)

        self.assertEqual([upset["match_id"] for upset in result], ["m7", "m6", "m8"])
        self.assertEqual([upset["rank"] for upset in result], [1, 2, 3])

    def test_unknown_score_still_counts(self) -> None:
        history = warm_up("alpha") + [rated_set(6, "alpha", "beta", 900.0, 1100.0, score=None)]

        [upset] = find_upsets(history)

        self.assertIsNone(upset["winner_score"])
        self.assertFalse(upset["score_known"])

    def test_thresholds_can_be_overridden(self) -> None:
        history = [rated_set(1, "alpha", "beta", 1000.0, 1050.0)]

        self.assertEqual(len(find_upsets(history, minimum_gap=50, minimum_prior_sets=0)), 1)

    def test_empty_history(self) -> None:
        self.assertEqual(find_upsets([]), [])


class UpsetDatabaseTests(unittest.TestCase):
    """Run the real Elo calculation on a temporary synthetic archive."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.db_path = root / "upsets.db"
        seed_path = root / "seed.json"
        seed_path.write_text(
            json.dumps({
                "players": [
                    {"player_id": "alpha", "display_name": "Alpha"},
                    {"player_id": "beta", "display_name": "Beta"},
                ],
                # Number 2 is played before number 1: the date decides the order.
                "tournaments": [
                    {"tournament_id": "wc_early", "tournament_number": 2,
                     "tournament_date": "2026-01-01", "winner_id": "alpha"},
                    {"tournament_id": "wc_late", "tournament_number": 1,
                     "tournament_date": "2026-02-01", "winner_id": "beta"},
                ],
            }),
            encoding="utf-8",
        )
        with redirect_stdout(StringIO()):
            initialize_database(
                self.db_path,
                DEFAULT_SCHEMA_PATH,
                seed_path,
                migrations_dir=DEFAULT_MIGRATIONS_DIR,
            )
        rows = [
            (f"early_{index}", "wc_early", "alpha", "beta", "alpha", 3, 0, 1, 0, index)
            for index in range(6)
        ] + [
            ("late_forfeit", "wc_late", "alpha", "beta", "beta", None, None, 0, 1, 1),
            ("late_upset", "wc_late", "alpha", "beta", "beta", 1, 2, 1, 0, 2),
        ]
        with sqlite3.connect(self.db_path) as connection, connection:
            connection.executemany(
                """
                INSERT INTO matches (
                    match_id, tournament_id, player_1_id, player_2_id, winner_id,
                    player_1_score, player_2_score, score_known, walkover,
                    suggested_play_order, stage, round_label
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'knockout', '1')
                """,
                rows,
            )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_archive_upset_uses_date_order_and_skips_forfeits(self) -> None:
        history = statistics.calculate_elo_history(self.db_path)
        before_upset = next(event for event in history if event["match_id"] == "late_upset")

        [upset] = get_upsets(self.db_path)

        self.assertEqual(upset["match_id"], "late_upset")
        self.assertEqual((upset["winner_id"], upset["loser_id"]), ("beta", "alpha"))
        self.assertEqual(upset["tournament_number"], 1)
        self.assertEqual(
            upset["elo_gap"],
            round(before_upset["loser_rating_before"] - before_upset["winner_rating_before"], 1),
        )
        self.assertGreaterEqual(upset["elo_gap"], 100)
        self.assertNotIn("late_forfeit", [event["match_id"] for event in history])

    def test_limit(self) -> None:
        self.assertEqual(len(get_upsets(self.db_path, limit=1)), 1)
        with self.assertRaisesRegex(ValueError, "limit must be greater than zero"):
            get_upsets(self.db_path, limit=0)

    def test_command_line_lists_upsets_by_gap(self) -> None:
        output = StringIO()
        with (
            patch.object(sys, "argv", ["smash_statistics.py", "--db", str(self.db_path), "--upsets"]),
            redirect_stdout(output),
        ):
            statistics.main()

        lines = output.getvalue().splitlines()
        self.assertIn("Biggest Elo Upsets", lines)
        header = next(line for line in lines if line.lstrip().startswith("Rank"))
        self.assertIn("Gap", header)
        [row] = [line for line in lines if line.strip().startswith("1 ")]
        self.assertIn("Beta", row)
        self.assertIn("2:1", row)

    def test_command_line_json_matches_get_upsets(self) -> None:
        output = StringIO()
        with (
            patch.object(
                sys, "argv",
                ["smash_statistics.py", "--db", str(self.db_path), "--upsets", "--json"],
            ),
            redirect_stdout(output),
        ):
            statistics.main()

        self.assertEqual(json.loads(output.getvalue()), get_upsets(self.db_path, limit=10))

    def test_command_line_reports_when_no_upset_exists(self) -> None:
        output = StringIO()
        with (
            patch.object(statistics, "get_upsets", lambda *args, **kwargs: []),
            patch.object(
                sys, "argv", ["smash_statistics.py", "--db", str(self.db_path), "--upsets"]
            ),
            redirect_stdout(output),
        ):
            statistics.main()

        self.assertIn("No upsets found (at least 150 Elo gap", output.getvalue())


class UpsetModuleBoundaryTests(unittest.TestCase):
    def test_facade_reexports_upset_functions(self) -> None:
        self.assertIs(statistics.get_upsets, upsets.get_upsets)
        self.assertIs(statistics.find_upsets, upsets.find_upsets)


if __name__ == "__main__":
    unittest.main()
