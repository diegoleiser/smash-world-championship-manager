"""Group Stage and bracket records count both archive stage spellings."""

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

import smash_statistics as statistics  # noqa: E402
from init_db import (  # noqa: E402
    DEFAULT_MIGRATIONS_DIR,
    DEFAULT_SCHEMA_PATH,
    initialize_database,
)


class PlayerPhaseRecordTests(unittest.TestCase):
    """Challonge stores group/knockout, Tournament Manager group_stage/bracket."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.db_path = root / "phases.db"
        seed_path = root / "seed.json"
        seed_path.write_text(
            json.dumps({
                "players": [
                    {"player_id": "alpha", "display_name": "Alpha"},
                    {"player_id": "beta", "display_name": "Beta"},
                ],
                "tournaments": [
                    {"tournament_id": "wc_01", "tournament_number": 1,
                     "tournament_date": "2026-01-01", "winner_id": "alpha"},
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
                """
                INSERT INTO matches (
                    match_id, tournament_id, player_1_id, player_2_id, winner_id,
                    player_1_score, player_2_score, score_known, walkover,
                    suggested_play_order, stage, round_label
                )
                VALUES (?, 'wc_01', 'alpha', 'beta', ?, 2, 1, 1, 0, ?, ?, '1')
                """,
                [
                    ("m1", "alpha", 1, "group"),
                    ("m2", "beta", 2, "group_stage"),
                    ("m3", "alpha", 3, "knockout"),
                    ("m4", "alpha", 4, "bracket"),
                ],
            )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_both_spellings_count_for_each_phase(self) -> None:
        stats = statistics.get_player_stats("alpha", self.db_path)

        self.assertEqual(
            (stats["group_matches"], stats["group_wins"], stats["group_losses"]),
            (2, 1, 1),
        )
        self.assertEqual(
            (stats["knockout_matches"], stats["knockout_wins"], stats["knockout_losses"]),
            (2, 2, 0),
        )


if __name__ == "__main__":
    unittest.main()
