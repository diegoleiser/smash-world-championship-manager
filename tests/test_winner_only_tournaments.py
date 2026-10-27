"""Tournaments where only the champion is known still count for that player."""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import milestones  # noqa: E402
import smash_statistics as statistics  # noqa: E402
from dashboard_pages.player import tournament_history_table  # noqa: E402
from init_db import (  # noqa: E402
    DEFAULT_MIGRATIONS_DIR,
    DEFAULT_SCHEMA_PATH,
    initialize_database,
)
from smash_stats.achievements import get_achievements  # noqa: E402
from smash_stats.database import KNOWN_PARTICIPANTS_SQL, connect_db  # noqa: E402
from text_format import format_ordinal  # noqa: E402


class WinnerOnlyTournamentTests(unittest.TestCase):
    """WC 02 has no participant or set records; only Beta's title is known."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.db_path = root / "winner_only.db"
        seed_path = root / "seed.json"
        seed_path.write_text(
            json.dumps({
                "players": [
                    {"player_id": player_id, "display_name": player_id.title()}
                    for player_id in ("alpha", "beta", "gamma")
                ],
                "tournaments": [
                    {"tournament_id": "wc_01", "tournament_number": 1,
                     "tournament_date": "2026-01-01", "winner_id": "alpha",
                     "match_data_available": True},
                    {"tournament_id": "wc_02", "tournament_number": 2,
                     "tournament_date": "2026-02-01", "winner_id": "beta",
                     "match_data_available": False},
                    {"tournament_id": "wc_03", "tournament_number": 3,
                     "tournament_date": "2026-03-01", "winner_id": "beta",
                     "match_data_available": True},
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
        with sqlite3.connect(self.db_path) as connection, connection:
            connection.executemany(
                "INSERT INTO tournament_participants (tournament_id, player_id, placement) "
                "VALUES (?, ?, ?)",
                [
                    ("wc_01", "alpha", 1), ("wc_01", "beta", 2), ("wc_01", "gamma", 3),
                    ("wc_03", "beta", 1), ("wc_03", "alpha", 2), ("wc_03", "gamma", 3),
                ],
            )
            connection.executemany(
                """
                INSERT INTO matches (
                    match_id, tournament_id, player_1_id, player_2_id, winner_id,
                    player_1_score, player_2_score, score_known, walkover,
                    suggested_play_order, stage, round_label
                )
                VALUES (?, ?, ?, ?, ?, 2, 0, 1, 0, ?, 'knockout', '1')
                """,
                [
                    ("m1", "wc_01", "alpha", "beta", "alpha", 1),
                    ("m2", "wc_03", "beta", "alpha", "beta", 1),
                ],
            )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_known_participants_add_only_the_missing_champion(self) -> None:
        with connect_db(self.db_path) as connection:
            rows = connection.execute(
                "SELECT tournament_id, player_id, placement, recorded FROM ("
                + KNOWN_PARTICIPANTS_SQL
                + ") ORDER BY tournament_id, player_id"
            ).fetchall()

        self.assertEqual(
            [tuple(row) for row in rows if row["tournament_id"] == "wc_02"],
            [("wc_02", "beta", 1, 0)],
        )
        self.assertEqual(len(rows), 7)

    def test_profile_and_history_count_the_title(self) -> None:
        stats = statistics.get_player_stats("beta", self.db_path)
        history = statistics.get_player_history("beta", self.db_path)

        self.assertEqual((stats["appearances"], stats["titles"]), (3, 2))
        self.assertEqual((stats["best_result"], stats["average_result"]), (1, 1.33))
        title = next(entry for entry in history if entry["tournament_number"] == 2)
        self.assertEqual((title["placement"], title["won_tournament"]), (1, True))
        self.assertFalse(title["match_data_available"])

    def test_history_table_shows_no_record_without_set_data(self) -> None:
        table = tournament_history_table(
            statistics.get_player_history("beta", self.db_path),
            format_ordinal,
        )

        wc_02 = next(row for row in table["rows"] if "WC 02" in row[0])
        self.assertEqual(wc_02[1:3], ["Champion", "–"])

    def test_hall_of_fame_counts_finals_podiums_and_appearances(self) -> None:
        records = {
            record["key"]: {
                entry["players"][0]["player_id"]: entry["value"]
                for entry in record["entries"]
            }
            for record in statistics.get_hall_of_fame(self.db_path)
        }

        self.assertEqual(records["most_finals"]["beta"], 3)
        self.assertEqual(records["most_podiums"]["beta"], 3)
        self.assertEqual(records["most_appearances"]["beta"], 3)

    def test_achievements_count_the_appearance_without_breaking_runs(self) -> None:
        unlocks = get_achievements(self.db_path)
        keys = {(entry["key"], entry["player_id"], entry["tournament_number"]) for entry in unlocks}

        self.assertIn(("appearances", "beta", 3), keys)
        self.assertIn(("breakthrough", "beta", 2), keys)
        self.assertNotIn(("breakthrough", "beta", 3), keys)
        self.assertIn(("podium_streak", "beta", 3), keys)
        # Gamma's result at WC 02 is unknown: it neither counts nor breaks the
        # run, so podiums at WC 01 and WC 03 are only two in a row.
        self.assertNotIn("podium_streak", {key for key, player, _ in keys if player == "gamma"})

    def test_milestones_compare_with_the_known_title(self) -> None:
        self.assertFalse(
            any(
                "Beta achieved a new career-best placement" in text
                for text in milestones.detect_tournament_milestones(self.db_path, 3)
            )
        )


if __name__ == "__main__":
    unittest.main()
