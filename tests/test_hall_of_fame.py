"""Hall of Fame records: positive all-time records with their top holders."""

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
from smash_stats import hall_of_fame  # noqa: E402
from smash_stats.hall_of_fame import (  # noqa: E402
    build_hall_of_fame,
    get_hall_of_fame,
    rank_candidates,
)


PLAYERS = {
    player_id: {"player": player_id.title()}
    for player_id in ("alpha", "beta", "gamma", "delta")
}


def rated_set(
    winner: str,
    loser: str,
    *,
    tournament_number: int = 1,
    winner_after: float = 1010.0,
    loser_after: float = 990.0,
    change: float = 10.0,
) -> dict:
    """One event shaped like calculate_elo_history() output."""

    return {
        "winner_id": winner,
        "loser_id": loser,
        "tournament_number": tournament_number,
        "winner_rating_after": winner_after,
        "loser_rating_after": loser_after,
        "rating_change": change,
    }


def snapshot(tournament_number: int, player_id: str, rank: int, elo: float) -> dict:
    """One entry shaped like get_elo_ranking_timeline() output."""

    return {
        "tournament_number": tournament_number,
        "player_id": player_id,
        "rank": rank,
        "elo": elo,
    }


def build(**overrides) -> dict[str, dict]:
    arguments = {
        "players": PLAYERS,
        "tournaments": [],
        "participants": [],
        "history": [],
        "timeline": [],
    }
    arguments.update(overrides)
    return {record["key"]: record for record in build_hall_of_fame(**arguments)}


def holders(record: dict) -> list[tuple[int, list[str], object]]:
    return [
        (
            entry["rank"],
            [player["player_id"] for player in entry["players"]],
            entry["value"],
        )
        for entry in record["entries"]
    ]


class RankCandidatesTests(unittest.TestCase):
    def candidate(self, name: str, value: float) -> dict:
        return {"sort_name": name, "value": value}

    def test_ties_share_a_rank_and_all_tied_holders_at_the_cut_off_stay(self) -> None:
        ranked = rank_candidates(
            [
                self.candidate("Echo", 1),
                self.candidate("Delta", 2),
                self.candidate("Alpha", 5),
                self.candidate("Charlie", 2),
                self.candidate("Bravo", 2),
            ],
            top_n=3,
        )

        self.assertEqual(
            [(entry["rank"], entry["value"]) for entry in ranked],
            [(1, 5), (2, 2), (2, 2), (2, 2)],
        )
        self.assertNotIn("sort_name", ranked[0])

    def test_zero_values_are_not_records(self) -> None:
        self.assertEqual(rank_candidates([self.candidate("Alpha", 0)]), [])


class BuildHallOfFameTests(unittest.TestCase):
    def test_every_record_is_positive_and_grouped(self) -> None:
        records = build_hall_of_fame(
            players=PLAYERS,
            tournaments=[],
            participants=[],
            history=[],
            timeline=[],
        )
        groups = {key for key, _ in hall_of_fame.HALL_OF_FAME_GROUPS}

        self.assertEqual(len(records), 15)
        self.assertTrue(all(record["group"] in groups for record in records))
        self.assertTrue(all(record["entries"] == [] for record in records))
        self.assertNotIn("longest_loss_streak", [record["key"] for record in records])

    def test_championships_use_winner_and_placements(self) -> None:
        records = build(
            tournaments=[
                {"tournament_number": 1, "winner_id": "alpha"},
                {"tournament_number": 2, "winner_id": "alpha"},
                {"tournament_number": 3, "winner_id": "beta"},
            ],
            participants=[
                {"tournament_number": 1, "player_id": "alpha", "placement": 1},
                {"tournament_number": 1, "player_id": "beta", "placement": 2},
                {"tournament_number": 1, "player_id": "gamma", "placement": 3},
                {"tournament_number": 2, "player_id": "alpha", "placement": 1},
                {"tournament_number": 2, "player_id": "gamma", "placement": 2},
                {"tournament_number": 2, "player_id": "delta", "placement": None},
                {"tournament_number": 3, "player_id": "beta", "placement": 1},
                {"tournament_number": 3, "player_id": "delta", "placement": 4},
            ],
        )

        self.assertEqual(
            holders(records["most_titles"]),
            [(1, ["alpha"], 2), (2, ["beta"], 1)],
        )
        self.assertEqual(
            holders(records["most_finals"]),
            [(1, ["alpha"], 2), (1, ["beta"], 2), (3, ["gamma"], 1)],
        )
        self.assertEqual(
            holders(records["most_podiums"]),
            [(1, ["alpha"], 2), (1, ["beta"], 2), (1, ["gamma"], 2)],
        )
        self.assertEqual(
            holders(records["most_appearances"]),
            [(1, ["alpha"], 2), (1, ["beta"], 2), (1, ["delta"], 2), (1, ["gamma"], 2)],
        )

    def test_set_records_and_win_streak_span(self) -> None:
        history = [
            rated_set("alpha", "beta", tournament_number=1),
            rated_set("alpha", "gamma", tournament_number=2),
            rated_set("alpha", "beta", tournament_number=3, winner_after=1100.0),
            rated_set("beta", "alpha", tournament_number=3, change=25.5),
            rated_set("alpha", "gamma", tournament_number=4),
            rated_set("alpha", "delta", tournament_number=4),
        ]

        records = build(history=history)

        self.assertEqual(holders(records["most_set_wins"])[0], (1, ["alpha"], 5))
        self.assertEqual(holders(records["most_sets_played"])[0], (1, ["alpha"], 6))
        self.assertEqual(
            holders(records["longest_win_streak"])[0],
            (1, ["alpha"], 3),
        )
        self.assertEqual(
            records["longest_win_streak"]["entries"][0]["detail"],
            "WC 01–WC 03",
        )
        peak = records["highest_peak_elo"]["entries"][0]
        self.assertEqual((peak["value"], peak["detail"]), (1100.0, "WC 03"))
        gain = records["biggest_set_elo_gain"]["entries"][0]
        self.assertEqual(
            (gain["players"][0]["player_id"], gain["value"], gain["detail"]),
            ("beta", 25.5, "vs Alpha · WC 03"),
        )

    def test_win_rate_needs_minimum_sets(self) -> None:
        history = [rated_set("alpha", "beta") for _ in range(4)] + [
            rated_set("beta", "alpha"),
            rated_set("gamma", "delta"),
        ]

        record = build(history=history)["highest_win_rate"]

        self.assertEqual(holders(record), [(1, ["alpha"], 80.0), (2, ["beta"], 20.0)])
        self.assertEqual(record["entries"][0]["detail"], "4–1 in Sets")

    def test_rivalries_are_pairs_and_h2h_streaks_cross_tournaments(self) -> None:
        history = [
            rated_set("alpha", "beta", tournament_number=1),
            rated_set("beta", "alpha", tournament_number=1),
            rated_set("beta", "alpha", tournament_number=2),
            rated_set("beta", "alpha", tournament_number=3),
            rated_set("alpha", "beta", tournament_number=3),
            rated_set("gamma", "delta", tournament_number=3),
        ]

        records = build(history=history)

        matchup = records["most_played_matchup"]["entries"][0]
        self.assertEqual(
            ([player["player_id"] for player in matchup["players"]], matchup["value"]),
            (["alpha", "beta"], 5),
        )
        self.assertEqual(matchup["detail"], "2:3")
        streak = records["longest_h2h_streak"]["entries"][0]
        self.assertEqual(
            ([player["player_id"] for player in streak["players"]], streak["value"]),
            (["beta", "alpha"], 3),
        )
        self.assertEqual(streak["detail"], "WC 01–WC 03")

    def test_elo_ranking_records(self) -> None:
        timeline = [
            snapshot(1, "alpha", 1, 1050.0),
            snapshot(1, "beta", 2, 1020.0),
            snapshot(1, "gamma", 3, 1000.0),
            snapshot(2, "beta", 1, 1100.0),
            snapshot(2, "alpha", 2, 1040.0),
            snapshot(2, "delta", 3, 990.0),
        ]

        records = build(timeline=timeline)

        self.assertEqual(
            holders(records["most_elo_rank_one"]),
            [(1, ["alpha"], 1), (1, ["beta"], 1)],
        )
        self.assertEqual(
            holders(records["most_elo_top_three"])[:2],
            [(1, ["alpha"], 2), (1, ["beta"], 2)],
        )
        lead = records["biggest_elo_lead"]["entries"]
        self.assertEqual(
            [(entry["players"][0]["player_id"], entry["value"]) for entry in lead],
            [("beta", 60.0), ("alpha", 30.0)],
        )
        self.assertEqual(lead[0]["detail"], "ahead of Alpha · WC 02")

    def test_only_eligible_players_hold_records(self) -> None:
        players = {key: PLAYERS[key] for key in ("alpha", "beta")}
        history = [rated_set("gamma", "alpha") for _ in range(3)] + [
            rated_set("alpha", "beta"),
        ]

        records = build(players=players, history=history)

        self.assertEqual(holders(records["most_set_wins"]), [(1, ["alpha"], 1)])
        self.assertEqual(
            [entry["players"][0]["player_id"] for entry in records["most_sets_played"]["entries"]],
            ["alpha", "beta"],
        )
        self.assertEqual(
            [
                [player["player_id"] for player in entry["players"]]
                for entry in records["most_played_matchup"]["entries"]
            ],
            [["alpha", "beta"]],
        )


class HallOfFameDatabaseTests(unittest.TestCase):
    """Run the loader on a temporary synthetic archive."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.db_path = root / "hall_of_fame.db"
        seed_path = root / "seed.json"
        seed_path.write_text(
            json.dumps({
                "players": [
                    {"player_id": "alpha", "display_name": "Alpha"},
                    {"player_id": "beta", "display_name": "Beta"},
                    {"player_id": "retired", "display_name": "Retired", "active": False},
                ],
                "tournaments": [
                    {"tournament_id": "wc_01", "tournament_number": 1,
                     "tournament_date": "2026-01-01", "winner_id": "retired"},
                    {"tournament_id": "wc_02", "tournament_number": 2,
                     "tournament_date": "2026-02-01", "winner_id": "alpha"},
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
            connection.execute("UPDATE players SET active = 0 WHERE player_id = 'retired'")
            connection.executemany(
                "INSERT INTO tournament_participants (tournament_id, player_id, placement) "
                "VALUES (?, ?, ?)",
                [
                    ("wc_01", "retired", 1), ("wc_01", "alpha", 2),
                    ("wc_02", "alpha", 1), ("wc_02", "beta", 2),
                ],
            )
            connection.executemany(
                """
                INSERT INTO matches (
                    match_id, tournament_id, player_1_id, player_2_id, winner_id,
                    player_1_score, player_2_score, score_known, walkover,
                    suggested_play_order, stage, round_label
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'knockout', '1')
                """,
                [
                    ("m1", "wc_01", "retired", "alpha", "retired", 2, 0, 1, 0, 1),
                    ("m2", "wc_02", "alpha", "beta", "alpha", 2, 1, 1, 0, 1),
                    ("m3", "wc_02", "alpha", "beta", "beta", None, None, 0, 1, 2),
                ],
            )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def records(self, **kwargs) -> dict[str, dict]:
        return {
            record["key"]: record
            for record in get_hall_of_fame(self.db_path, **kwargs)
        }

    def test_walkovers_do_not_count_as_sets(self) -> None:
        records = self.records()

        self.assertEqual(
            holders(records["most_sets_played"]),
            [(1, ["alpha"], 2), (2, ["beta"], 1), (2, ["retired"], 1)],
        )
        self.assertNotIn(
            "beta",
            [entry["players"][0]["player_id"] for entry in records["most_set_wins"]["entries"]],
        )

    def test_inactive_players_are_hidden_on_request(self) -> None:
        self.assertIn(
            (1, ["retired"], 1),
            holders(self.records()["most_titles"]),
        )
        active = self.records(active_only=True)
        self.assertEqual(holders(active["most_titles"]), [(1, ["alpha"], 1)])
        self.assertEqual(holders(active["most_finals"]), [(1, ["alpha"], 2), (2, ["beta"], 1)])

    def test_empty_archive_has_no_record_holders(self) -> None:
        with sqlite3.connect(self.db_path) as connection, connection:
            for table in ("matches", "tournament_participants", "tournaments"):
                connection.execute(f"DELETE FROM {table}")

        self.assertTrue(all(record["entries"] == [] for record in self.records().values()))

    def test_facade_reexports_hall_of_fame(self) -> None:
        self.assertIs(statistics.get_hall_of_fame, hall_of_fame.get_hall_of_fame)


if __name__ == "__main__":
    unittest.main()
