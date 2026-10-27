"""Achievements: lasting positive awards computed from the archive."""

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
from dashboard_pages.achievements import (  # noqa: E402
    player_unlock_history_html,
    tournament_unlock_groups,
    unlock_help,
    unlock_label,
)
from init_db import (  # noqa: E402
    DEFAULT_MIGRATIONS_DIR,
    DEFAULT_SCHEMA_PATH,
    initialize_database,
)
from smash_stats import achievements  # noqa: E402
from smash_stats.achievements import (  # noqa: E402
    ACHIEVEMENTS,
    build_achievements,
    get_achievements,
    losers_side_finalist,
    summarize_achievements,
)


PLAYERS = {
    player_id: {"player": player_id.title()}
    for player_id in ("alpha", "beta", "gamma", "delta")
}


def tournament(number: int, winner: str | None) -> dict:
    return {
        "tournament_number": number,
        "tournament_date": f"2026-{number:02d}-01",
        "winner_id": winner,
    }


def rated_set(
    winner: str,
    loser: str,
    *,
    tournament_number: int = 1,
    sequence: int = 1,
    winner_before: float = 1000.0,
    loser_before: float = 1000.0,
) -> dict:
    """One event shaped like calculate_elo_history() output."""

    return {
        "sequence": sequence,
        "match_id": f"m{sequence}",
        "tournament_id": f"wc_{tournament_number:02d}",
        "tournament_number": tournament_number,
        "tournament_date": f"2026-{tournament_number:02d}-01",
        "stage": "bracket",
        "round_label": "",
        "winner_id": winner,
        "winner": winner.title(),
        "loser_id": loser,
        "loser": loser.title(),
        "winner_score": 2,
        "loser_score": 0,
        "score_known": True,
        "rating_change": 10.0,
        "winner_rating_before": winner_before,
        "loser_rating_before": loser_before,
        "winner_rating_after": winner_before + 10.0,
        "loser_rating_after": loser_before - 10.0,
    }


def build(**overrides) -> list[dict]:
    arguments = {
        "players": PLAYERS,
        "tournaments": [],
        "participants": [],
        "history": [],
        "timeline": [],
    }
    arguments.update(overrides)
    return build_achievements(**arguments)


def unlocked(entries: list[dict]) -> set[tuple[str, str, int]]:
    return {
        (entry["key"], entry["player_id"], entry["tournament_number"])
        for entry in entries
    }


def tiers(entries: list[dict], key: str, player_id: str) -> list[tuple[int, int]]:
    return [
        (entry["tier"], entry["tournament_number"])
        for entry in entries
        if entry["key"] == key and entry["player_id"] == player_id
    ]


class CatalogueTests(unittest.TestCase):
    def test_keys_are_unique_and_groups_known(self) -> None:
        keys = [achievement["key"] for achievement in ACHIEVEMENTS]
        groups = {group for group, _title in achievements.ACHIEVEMENT_GROUPS}

        self.assertEqual(len(keys), len(set(keys)))
        self.assertTrue(all(achievement["group"] in groups for achievement in ACHIEVEMENTS))

    def test_tiers_have_three_rising_thresholds(self) -> None:
        for achievement in ACHIEVEMENTS:
            if "tiers" in achievement:
                thresholds = [threshold for threshold, _title in achievement["tiers"]]
                self.assertEqual(len(thresholds), 3)
                self.assertEqual(thresholds, sorted(set(thresholds)))


class BuildAchievementsTests(unittest.TestCase):
    def test_empty_archive_unlocks_nothing(self) -> None:
        self.assertEqual(build(), [])

    def test_titles_defense_and_three_peat(self) -> None:
        entries = build(
            tournaments=[
                tournament(1, "alpha"),
                tournament(2, "alpha"),
                tournament(3, "alpha"),
                tournament(4, "beta"),
                tournament(5, "alpha"),
                tournament(6, "alpha"),
            ],
        )

        self.assertEqual(
            unlocked(entries),
            {
                ("first_title", "alpha", 1),
                ("title_defense", "alpha", 2),
                ("title_defense", "alpha", 3),
                ("three_peat", "alpha", 3),
                ("first_title", "beta", 4),
                ("title_defense", "alpha", 6),
            },
        )
        self.assertEqual(
            [entry["occurrence"] for entry in entries if entry["key"] == "title_defense"],
            [1, 2, 3],
        )

    def test_title_streak_follows_dates_not_numbers(self) -> None:
        first, second = tournament(1, "alpha"), tournament(2, "alpha")
        later = tournament(3, "beta")
        later["tournament_date"] = "2026-01-15"

        entries = build(tournaments=[first, second, later])

        self.assertNotIn(("title_defense", "alpha", 2), unlocked(entries))

    def test_placements_and_appearances_unlock_once(self) -> None:
        tournaments = [tournament(number, None) for number in range(1, 11)]
        participants = [
            {"tournament_number": number, "player_id": "beta",
             "placement": 3 if number in (2, 4) else (2 if number == 6 else 5)}
            for number in range(1, 11)
        ]

        entries = build(tournaments=tournaments, participants=participants)

        self.assertEqual(
            unlocked(entries),
            {
                ("first_podium", "beta", 2),
                ("breakthrough", "beta", 2),
                ("appearances", "beta", 3),
                ("appearances", "beta", 5),
                ("first_final", "beta", 6),
                ("breakthrough", "beta", 6),
                ("appearances", "beta", 10),
            },
        )
        self.assertEqual(tiers(entries, "appearances", "beta"), [(1, 3), (2, 5), (3, 10)])
        self.assertEqual(
            [entry["title"] for entry in entries if entry["key"] == "appearances"],
            ["Regular", "Mainstay", "Veteran"],
        )
        self.assertEqual(
            next(entry for entry in entries if entry["key"] == "appearances")["description"],
            "Played 3 World Championships.",
        )

    def test_flawless_champion_and_perfect_group_stage(self) -> None:
        group = [
            dict(rated_set("alpha", loser, sequence=index), stage="group")
            for index, loser in enumerate(("beta", "gamma", "delta"), start=1)
        ]
        history = group + [
            rated_set("alpha", "beta", sequence=4),
            rated_set("beta", "alpha", sequence=5, tournament_number=2),
        ]

        entries = build(
            tournaments=[tournament(1, "alpha"), tournament(2, "alpha")],
            participants=[
                {"tournament_number": number, "player_id": "alpha", "placement": 1}
                for number in (1, 2)
            ],
            history=history,
        )
        keys = unlocked(entries)

        self.assertIn(("flawless_champion", "alpha", 1), keys)
        self.assertNotIn(("flawless_champion", "alpha", 2), keys)
        self.assertIn(("perfect_group_stage", "alpha", 1), keys)
        self.assertEqual(
            next(entry for entry in entries if entry["key"] == "perfect_group_stage")["detail"],
            "3–0 in Sets",
        )

    def test_podium_streak_and_underdog_podium(self) -> None:
        tournaments = [tournament(number, None) for number in range(1, 6)]
        placements = {1: 9, 2: 9, 3: 2, 4: 1, 5: 3}
        participants = [
            {"tournament_number": number, "player_id": "beta",
             "placement": placements[number], "seed": 7 if number == 5 else 1}
            for number in range(1, 6)
        ] + [
            {"tournament_number": number, "player_id": f"other{index}",
             "placement": index + 1, "seed": index + 1}
            for number in range(1, 6)
            for index in range(9)
        ]
        # A tournament without placements does not break the run.
        tournaments.insert(4, tournament(9, None))
        tournaments[4]["tournament_date"] = "2026-04-15"

        entries = build(tournaments=tournaments, participants=participants)

        self.assertEqual(
            [(entry["key"], entry["tournament_number"]) for entry in entries
             if entry["player_id"] == "beta" and entry["key"] in {"podium_streak", "underdog_podium"}],
            [("podium_streak", 5), ("underdog_podium", 5)],
        )
        self.assertEqual(
            next(entry for entry in entries if entry["key"] == "underdog_podium")["detail"],
            "Seed 7 of 10 · finished 3rd",
        )

    def test_curse_breaker_needs_three_straight_losses(self) -> None:
        history = [
            rated_set("alpha", "beta", sequence=1),
            rated_set("alpha", "beta", sequence=2),
            rated_set("beta", "alpha", sequence=3),
            rated_set("alpha", "beta", sequence=4),
            rated_set("alpha", "beta", sequence=5),
            rated_set("alpha", "beta", sequence=6),
            rated_set("beta", "alpha", sequence=7, tournament_number=2),
        ]

        entries = build(
            tournaments=[tournament(1, None), tournament(2, None)],
            history=history,
        )

        self.assertEqual(
            [(entry["player_id"], entry["tournament_number"], entry["detail"])
             for entry in entries if entry["key"] == "curse_breaker"],
            [("beta", 2, "vs Alpha after 3 losses in a row")],
        )

    def test_breakthrough_needs_a_better_placement_than_ever_before(self) -> None:
        placements = {1: 5, 2: 7, 3: 4, 4: 4, 5: 2}
        entries = build(
            tournaments=[tournament(number, None) for number in placements],
            participants=[
                {"tournament_number": number, "player_id": "gamma", "placement": placement}
                for number, placement in placements.items()
            ],
        )

        self.assertEqual(
            [(entry["tournament_number"], entry["occurrence"], entry["detail"])
             for entry in entries if entry["key"] == "breakthrough"],
            [
                (3, 1, "Finished 4th (previous best 5th)"),
                (5, 2, "Finished 2nd (previous best 4th)"),
            ],
        )

    def test_seed_buster_needs_four_seeds_difference(self) -> None:
        participants = [
            {"tournament_number": 1, "player_id": player_id, "placement": None, "seed": seed}
            for player_id, seed in (("alpha", 1), ("beta", 4), ("gamma", 5), ("delta", 8))
        ]
        history = [
            rated_set("beta", "alpha", sequence=1),
            rated_set("gamma", "alpha", sequence=2),
            rated_set("delta", "gamma", sequence=3),
        ]

        entries = build(
            tournaments=[tournament(1, None)],
            participants=participants,
            history=history,
        )

        self.assertEqual(
            [(entry["player_id"], entry["detail"])
             for entry in entries if entry["key"] == "seed_buster"],
            [("gamma", "vs Alpha (Seed 5 vs 1)")],
        )

    def test_game_off_the_champion_once_with_a_game_won(self) -> None:
        swept = rated_set("alpha", "beta", sequence=1)
        close = dict(rated_set("alpha", "gamma", sequence=2), loser_score=1)
        later = dict(rated_set("alpha", "gamma", sequence=3, tournament_number=2), loser_score=1)
        not_champion = dict(rated_set("beta", "delta", sequence=4), loser_score=1)

        entries = build(
            tournaments=[tournament(1, "alpha"), tournament(2, "alpha")],
            history=[swept, close, later, not_champion],
        )

        self.assertEqual(
            [(entry["player_id"], entry["tournament_number"], entry["detail"])
             for entry in entries if entry["key"] == "game_off_the_champion"],
            [("gamma", 1, "1–2 vs Alpha")],
        )

    def test_elo_peak_tiers_follow_the_winner_rating(self) -> None:
        history = [
            dict(rated_set("alpha", "beta", sequence=1), winner_rating_after=1120.0),
            dict(rated_set("alpha", "beta", sequence=2, tournament_number=2),
                 winner_rating_after=1210.0),
        ]

        entries = build(
            tournaments=[tournament(1, None), tournament(2, None)],
            history=history,
        )

        self.assertEqual(tiers(entries, "elo_peak", "alpha"), [(1, 1), (2, 2), (3, 2)])

    def test_top_three_scalp_uses_the_ranking_before_the_tournament(self) -> None:
        timeline = [
            {"tournament_number": 1, "player_id": "alpha", "rank": 1},
            {"tournament_number": 1, "player_id": "beta", "rank": 4},
        ]
        history = [
            rated_set("beta", "alpha", sequence=1, tournament_number=1),
            rated_set("gamma", "beta", sequence=2, tournament_number=2),
            rated_set("gamma", "alpha", sequence=3, tournament_number=2),
        ]

        entries = build(
            tournaments=[tournament(1, None), tournament(2, None)],
            history=history,
            timeline=timeline,
        )
        scalps = [entry for entry in entries if entry["key"] == "top_three_scalp"]

        self.assertEqual(
            [(entry["player_id"], entry["tournament_number"], entry["detail"]) for entry in scalps],
            [("gamma", 2, "vs Alpha (Elo #1)")],
        )

    def test_set_win_thresholds_count_rated_sets(self) -> None:
        history = [
            rated_set("alpha", "beta", sequence=index, tournament_number=1 if index <= 30 else 2)
            for index in range(1, 51)
        ]

        entries = build(
            tournaments=[tournament(1, None), tournament(2, None)],
            history=history,
        )

        self.assertEqual(tiers(entries, "set_wins", "alpha"), [(1, 1), (2, 2)])

    def test_giant_killer_counts_every_upset_with_detail(self) -> None:
        warm_up = [
            rated_set("gamma", "delta", sequence=index)
            for index in range(1, 6)
        ]
        history = warm_up + [
            rated_set("gamma", "alpha", sequence=6, tournament_number=1,
                      winner_before=1000.0, loser_before=1160.0),
            rated_set("gamma", "alpha", sequence=7, tournament_number=2,
                      winner_before=1000.0, loser_before=1300.0),
        ]

        entries = build(
            tournaments=[tournament(1, None), tournament(2, None)],
            history=history,
        )
        giant_killer = [entry for entry in entries if entry["key"] == "giant_killer"]

        self.assertEqual(
            [
                (entry["occurrence"], entry["tournament_number"], entry["detail"])
                for entry in giant_killer
            ],
            [(1, 1, "vs Alpha · +160.0 Elo"), (2, 2, "vs Alpha · +300.0 Elo")],
        )

    def test_elo_rank_achievements_use_the_timeline(self) -> None:
        timeline = [
            {"tournament_number": 1, "player_id": "alpha", "rank": 1},
            {"tournament_number": 1, "player_id": "beta", "rank": 4},
            {"tournament_number": 2, "player_id": "beta", "rank": 3},
            {"tournament_number": 3, "player_id": "beta", "rank": 1},
        ]

        entries = build(
            tournaments=[tournament(number, None) for number in (1, 2, 3)],
            timeline=timeline,
        )

        self.assertEqual(
            unlocked(entries),
            {
                ("elo_rank_one", "alpha", 1),
                ("elo_top_three", "alpha", 1),
                ("elo_top_three", "beta", 2),
                ("elo_rank_one", "beta", 3),
            },
        )

    def test_losers_run_and_comeback_champion(self) -> None:
        entries = build(
            tournaments=[tournament(1, "beta"), tournament(2, "alpha")],
            losers_finalists={1: "beta", 2: "gamma"},
        )

        self.assertEqual(
            unlocked(entries),
            {
                ("first_title", "beta", 1),
                ("losers_run", "beta", 1),
                ("comeback_champion", "beta", 1),
                ("first_title", "alpha", 2),
                ("losers_run", "gamma", 2),
            },
        )

    def test_entries_carry_catalogue_text_and_date_in_order(self) -> None:
        entries = build(
            tournaments=[tournament(2, "beta"), tournament(1, "alpha")],
        )

        self.assertEqual([entry["player_id"] for entry in entries], ["alpha", "beta"])
        self.assertEqual(entries[0]["title"], "First Title")
        self.assertEqual(entries[0]["tournament_date"], "2026-01-01")
        self.assertTrue(entries[0]["description"])

    def test_unknown_players_are_ignored(self) -> None:
        self.assertEqual(build(tournaments=[tournament(1, "ghost")]), [])


class SummarizeAchievementsTests(unittest.TestCase):
    def test_badges_keep_top_tier_count_and_rarity(self) -> None:
        tournaments = [tournament(number, "alpha") for number in range(1, 6)]
        participants = [
            {"tournament_number": number, "player_id": player_id, "placement": None}
            for number in range(1, 6)
            for player_id in ("alpha", "beta", "gamma")
            if player_id != "gamma" or number <= 3
        ]

        badges = {
            (badge["player_id"], badge["key"]): badge
            for badge in summarize_achievements(
                build(tournaments=tournaments, participants=participants)
            )
        }

        alpha_defense = badges[("alpha", "title_defense")]
        self.assertEqual(alpha_defense["count"], 4)
        self.assertEqual(alpha_defense["first"]["tournament_number"], 2)
        self.assertEqual(alpha_defense["latest"]["tournament_number"], 5)
        self.assertTrue(alpha_defense["rare"])

        alpha_appearances = badges[("alpha", "appearances")]
        self.assertEqual(
            (alpha_appearances["title"], alpha_appearances["tier_name"]),
            ("Mainstay", "Silver"),
        )
        self.assertEqual(alpha_appearances["latest"]["tournament_number"], 5)
        self.assertEqual(alpha_appearances["holders"], 2)
        # Gamma reached only the first tier; Alpha and Beta count for it too.
        self.assertEqual(badges[("gamma", "appearances")]["holders"], 3)
        self.assertFalse(badges[("gamma", "appearances")]["rare"])


class PlayerUnlockHistoryTests(unittest.TestCase):
    def test_repeats_list_every_time_with_detail(self) -> None:
        warm_up = [rated_set("gamma", "delta", sequence=index) for index in range(1, 6)]
        unlocks = build(
            tournaments=[tournament(1, None), tournament(2, None)],
            history=warm_up + [
                rated_set("gamma", "alpha", sequence=6, loser_before=1160.0),
                rated_set("gamma", "beta", sequence=7, tournament_number=2,
                          loser_before=1300.0),
            ],
        )

        markup = player_unlock_history_html(unlocks, "giant_killer", "gamma")

        self.assertIn('data-label="Detail"', markup)
        self.assertIn("vs Alpha · +160.0 Elo", markup)
        self.assertIn("vs Beta · +300.0 Elo", markup)
        self.assertIn("/tournaments?tournament=2", markup)

    def test_tiers_list_each_level_and_single_unlocks_need_no_table(self) -> None:
        participants = [
            {"tournament_number": number, "player_id": "beta", "placement": None}
            for number in range(1, 6)
        ]
        unlocks = build(
            tournaments=[tournament(number, None) for number in range(1, 6)],
            participants=participants,
        )

        markup = player_unlock_history_html(unlocks, "appearances", "beta")

        self.assertIn("Regular (Bronze)", markup)
        self.assertIn("Mainstay (Silver)", markup)
        self.assertNotIn('data-label="Detail"', markup)
        self.assertIsNone(
            player_unlock_history_html(
                build(tournaments=[tournament(1, "beta")]), "first_title", "beta"
            )
        )


class TournamentUnlockGroupsTests(unittest.TestCase):
    def test_players_follow_standings(self) -> None:
        unlocks = build(
            tournaments=[tournament(1, "beta")],
            participants=[
                {"tournament_number": 1, "player_id": player_id, "placement": placement}
                for player_id, placement in (("beta", 1), ("alpha", 2), ("gamma", 3))
            ],
        )

        groups = tournament_unlock_groups(unlocks, 1, ["beta", "alpha", "gamma"])

        self.assertEqual(
            [
                (player["player"], [unlock_label(entry) for entry in entries])
                for player, entries in groups
            ],
            [
                ("Beta", ["First Title", "First Final", "First Podium"]),
                ("Alpha", ["First Final", "First Podium"]),
                ("Gamma", ["First Podium"]),
            ],
        )

    def test_help_adds_rarity_tier_repeat_and_context(self) -> None:
        entry = {
            "description": "Won a rated Set against a player rated at least 150 Elo higher.",
            "tier": None,
            "occurrence": 2,
            "detail": "vs Alpha · +160.0 Elo",
            "title": "Giant Killer",
        }

        self.assertEqual(unlock_label(entry), "Giant Killer ×2")
        self.assertEqual(
            unlock_help(entry, rare=True),
            "Won a rated Set against a player rated at least 150 Elo higher. "
            "Rare. 2nd time. vs Alpha · +160.0 Elo.",
        )

    def test_no_unlocks_means_no_groups(self) -> None:
        self.assertEqual(tournament_unlock_groups([], 1, []), [])


class LosersSideFinalistTests(unittest.TestCase):
    def match(self, match_type: str, player_1: str, player_2: str, winner: str) -> dict:
        return {
            "match_type": match_type,
            "player_1_id": player_1,
            "player_2_id": player_2,
            "winner_id": winner,
        }

    def test_losers_final_winner_is_the_finalist(self) -> None:
        bracket = [
            self.match("winners_final", "alpha", "beta", "alpha"),
            self.match("losers_final", "beta", "gamma", "gamma"),
            self.match("grand_final", "alpha", "gamma", "alpha"),
        ]
        self.assertEqual(losers_side_finalist(bracket), "gamma")

    def test_falls_back_to_winners_final_without_losers_final(self) -> None:
        bracket = [
            self.match("winners_final", "alpha", "beta", "alpha"),
            self.match("grand_final", "alpha", "beta", "beta"),
        ]
        self.assertEqual(losers_side_finalist(bracket), "beta")

    def test_no_grand_final_means_no_finalist(self) -> None:
        self.assertIsNone(losers_side_finalist([]))


class AchievementsDatabaseTests(unittest.TestCase):
    """Run the loader on a temporary archive with both bracket formats."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.db_path = root / "achievements.db"
        seed_path = root / "seed.json"
        seed_path.write_text(
            json.dumps({
                "players": [
                    {"player_id": player_id, "display_name": player_id.title()}
                    for player_id in ("alpha", "beta", "gamma", "delta")
                ],
                "tournaments": [
                    {"tournament_id": "wc_01", "tournament_number": 1,
                     "tournament_date": "2026-01-01", "winner_id": "beta"},
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
            connection.executemany(
                "INSERT INTO tournament_participants (tournament_id, player_id, placement) "
                "VALUES (?, ?, ?)",
                [
                    ("wc_01", "beta", 1), ("wc_01", "alpha", 2),
                    ("wc_01", "gamma", 3), ("wc_01", "delta", 4),
                    ("wc_02", "alpha", 1), ("wc_02", "gamma", 2),
                    ("wc_02", "beta", 3), ("wc_02", "delta", 4),
                ],
            )
            # WC 01: Tournament Manager bracket, labels carry the match code.
            connection.executemany(
                """
                INSERT INTO matches (
                    match_id, tournament_id, player_1_id, player_2_id, winner_id,
                    player_1_score, player_2_score, score_known, walkover,
                    suggested_play_order, stage, round_label
                )
                VALUES (?, 'wc_01', ?, ?, ?, ?, ?, 1, ?, ?, 'bracket', ?)
                """,
                [
                    ("t1", "alpha", "beta", "alpha", 2, 0, 0, 1, "Winners Round 1 (W1M1)"),
                    ("t2", "gamma", "delta", "gamma", 2, 0, 0, 2, "Winners Round 1 (W1M2)"),
                    ("t3", "alpha", "gamma", "alpha", 2, 1, 0, 3, "Winners Final (WF)"),
                    ("t4", "beta", "delta", "beta", None, None, 1, 4, "Losers Round 1 (L1M1)"),
                    ("t5", "beta", "gamma", "beta", 2, 1, 0, 5, "Losers Final (LF)"),
                    ("t6", "alpha", "beta", "beta", 1, 2, 0, 6, "Grand Final (GF)"),
                    ("t7", "alpha", "beta", "beta", 0, 2, 0, 7, "Grand Final Reset (GFR)"),
                ],
            )
            # WC 02: historical Challonge knockout, losers rounds are negative.
            connection.executemany(
                """
                INSERT INTO matches (
                    match_id, tournament_id, player_1_id, player_2_id, winner_id,
                    player_1_score, player_2_score, score_known, walkover,
                    suggested_play_order, stage, round_label,
                    challonge_identifier, challonge_round
                )
                VALUES (?, 'wc_02', ?, ?, ?, 2, 0, 1, 0, ?, 'knockout', '', ?, ?)
                """,
                [
                    ("c1", "alpha", "beta", "alpha", 1, "A", 1),
                    ("c2", "gamma", "delta", "gamma", 2, "B", 1),
                    ("c3", "alpha", "gamma", "alpha", 3, "C", 2),
                    ("c4", "beta", "delta", "beta", 4, "D", -1),
                    ("c5", "gamma", "beta", "gamma", 5, "E", -2),
                    ("c6", "alpha", "gamma", "alpha", 6, "F", 3),
                ],
            )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_both_bracket_formats_find_the_losers_finalist(self) -> None:
        keys = unlocked(get_achievements(self.db_path))

        self.assertIn(("losers_run", "beta", 1), keys)
        self.assertIn(("comeback_champion", "beta", 1), keys)
        self.assertIn(("losers_run", "gamma", 2), keys)
        self.assertNotIn(("comeback_champion", "gamma", 2), keys)

    def test_empty_archive_unlocks_nothing(self) -> None:
        with sqlite3.connect(self.db_path) as connection, connection:
            for table in ("matches", "tournament_participants", "tournaments"):
                connection.execute(f"DELETE FROM {table}")

        self.assertEqual(get_achievements(self.db_path), [])

    def add_wc_02_wins(self, start: int, count: int, *, walkover: bool = False) -> None:
        with sqlite3.connect(self.db_path) as connection, connection:
            connection.executemany(
                """
                INSERT INTO matches (
                    match_id, tournament_id, player_1_id, player_2_id, winner_id,
                    score_known, walkover, suggested_play_order, stage, round_label
                )
                VALUES (?, 'wc_02', 'alpha', 'delta', 'alpha', 0, ?, ?, 'group', 'Group A')
                """,
                [
                    (f"extra{index}", int(walkover), 100 + index)
                    for index in range(start, start + count)
                ],
            )

    def test_set_win_milestone_and_achievement_ignore_walkovers(self) -> None:
        # Alpha has 5 rated wins in the bracket fixtures; 19 more make 24.
        self.add_wc_02_wins(0, 19)
        self.add_wc_02_wins(19, 1, walkover=True)

        self.assertFalse(
            any("25 recorded set wins" in text
                for text in milestones.detect_tournament_milestones(self.db_path, 2))
        )
        self.assertEqual(tiers(get_achievements(self.db_path), "set_wins", "alpha"), [])

        self.add_wc_02_wins(20, 1)

        self.assertIn(
            "Alpha reached 25 recorded set wins.",
            milestones.detect_tournament_milestones(self.db_path, 2),
        )
        self.assertEqual(tiers(get_achievements(self.db_path), "set_wins", "alpha"), [(1, 2)])

    def test_facade_reexports_achievements(self) -> None:
        self.assertIs(statistics.get_achievements, achievements.get_achievements)


if __name__ == "__main__":
    unittest.main()
