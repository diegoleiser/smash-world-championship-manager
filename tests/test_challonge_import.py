"""Characterize the Challonge importer with synthetic payloads only.

Every test uses a temporary database, raw directory and override directory.
The private ``data/`` directory is never read or written.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import challonge_import  # noqa: E402
from init_db import (  # noqa: E402
    DEFAULT_MIGRATIONS_DIR,
    DEFAULT_SCHEMA_PATH,
    initialize_database,
)


TOURNAMENT_ID = "wc_01"
PLAYERS = (
    ("alpha", "Alpha", ["Alpha", "Alpha Old"]),
    ("beta", "Beta", ["Beta"]),
    ("gamma", "Gamma", ["Gamma"]),
    ("delta", "Delta", ["Delta"]),
)


def participants_payload() -> list[dict]:
    """Challonge v1 participants; group IDs map to the same players."""

    return [
        {"participant": {"id": 101, "name": "Alpha Old", "final_rank": 1, "seed": 1, "group_player_ids": [201]}},
        {"participant": {"id": 102, "name": " beta ", "final_rank": 2, "seed": 2, "group_player_ids": [202]}},
        {"participant": {"id": 103, "name": "Gamma", "final_rank": 3, "seed": 3, "group_player_ids": [203]}},
        {"participant": {"id": 104, "name": "DELTA", "final_rank": 4, "seed": 4, "group_player_ids": [204]}},
    ]


def matches_payload() -> list[dict]:
    """One group Set, Winners and Losers Sets, an unknown score and a forfeit."""

    return [
        {"match": {
            "id": 1, "identifier": "A", "group_id": 9, "round": 1, "state": "complete",
            "player1_id": 201, "player2_id": 202, "winner_id": 201, "scores_csv": "2-1",
            "suggested_play_order": 1, "completed_at": "2026-01-01T12:00:00Z",
        }},
        {"match": {
            "id": 2, "identifier": "B", "group_id": None, "round": 1, "state": "complete",
            "player1_id": 101, "player2_id": 104, "winner_id": 101, "scores_csv": "3-0",
        }},
        {"match": {
            "id": 3, "identifier": "C", "group_id": None, "round": -1, "state": "complete",
            "player1_id": 103, "player2_id": 104, "winner_id": 103, "scores_csv": "0-0",
        }},
        {"match": {
            "id": 4, "identifier": "D", "group_id": None, "round": 2, "state": "complete",
            "player1_id": 102, "player2_id": 103, "winner_id": 102, "scores_csv": None,
            "forfeited": True,
        }},
    ]


class ChallongeImportTestCase(unittest.TestCase):
    """Create a fresh seeded database and isolate module paths."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.db_path = root / "import.db"
        self.raw_dir = root / "raw"
        self.override_dir = root / "overrides"
        self.override_dir.mkdir()
        seed_path = root / "seed.json"
        seed_path.write_text(
            json.dumps({
                "players": [
                    {"player_id": player_id, "display_name": name, "aliases": aliases}
                    for player_id, name, aliases in PLAYERS
                ],
                "tournaments": [{
                    "tournament_id": TOURNAMENT_ID,
                    "tournament_number": 1,
                    "tournament_date": "2026-01-01",
                    "winner_id": "alpha",
                }],
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
        self.patches = [
            patch.object(challonge_import, "DB_PATH", self.db_path),
            patch.object(challonge_import, "RAW_DIR", self.raw_dir),
            patch.object(challonge_import, "OVERRIDE_DIR", self.override_dir),
        ]
        for active_patch in self.patches:
            active_patch.start()

    def tearDown(self) -> None:
        for active_patch in self.patches:
            active_patch.stop()
        self.temporary_directory.cleanup()

    def run_import(self, participants=None, matches=None, **kwargs) -> dict:
        return challonge_import.import_payloads(
            TOURNAMENT_ID,
            participants_payload() if participants is None else participants,
            matches_payload() if matches is None else matches,
            **kwargs,
        )

    def table_rows(self) -> dict[str, list[tuple]]:
        with sqlite3.connect(self.db_path) as connection:
            return {
                "participants": connection.execute(
                    "SELECT player_id, placement, seed FROM tournament_participants ORDER BY player_id"
                ).fetchall(),
                "matches": connection.execute(
                    """
                    SELECT match_id, round_label, bracket_side, player_1_id, player_2_id,
                           winner_id, player_1_score, player_2_score, score_known, walkover,
                           source, stage, challonge_match_id, challonge_identifier,
                           challonge_group_id, challonge_round, suggested_play_order,
                           completed_at
                    FROM matches ORDER BY match_id
                    """
                ).fetchall(),
                "tournament": connection.execute(
                    "SELECT bracket_source, match_data_available FROM tournaments"
                ).fetchall(),
            }

    def write_override(self, payload: dict) -> Path:
        path = self.override_dir / f"{TOURNAMENT_ID}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path


class ImportPayloadTests(ChallongeImportTestCase):
    """Import behavior when no override file exists."""

    EXPECTED_MATCHES = [
        ("wc_01_challonge_1", "1", "round_robin", "alpha", "beta", "alpha", 2, 1, 1, 0,
         "challonge", "group", "1", "A", "9", 1, 1, "2026-01-01T12:00:00Z"),
        ("wc_01_challonge_2", "1", "winners", "alpha", "delta", "alpha", 3, 0, 1, 0,
         "challonge", "knockout", "2", "B", None, 1, None, None),
        ("wc_01_challonge_3", "-1", "losers", "gamma", "delta", "gamma", None, None, 0, 0,
         "challonge", "knockout", "3", "C", None, -1, None, None),
        ("wc_01_challonge_4", "2", "winners", "beta", "gamma", "beta", None, None, 0, 1,
         "challonge", "knockout", "4", "D", None, 2, None, None),
    ]

    def test_imports_participants_matches_and_marks_tournament(self) -> None:
        result = self.run_import()

        self.assertEqual(
            result,
            {
                "tournament_id": TOURNAMENT_ID, "backup_path": None,
                "participants": 4, "matches": 4, "group_matches": 1,
                "knockout_matches": 3, "scores_known": 2, "scores_unknown": 2,
                "unknown_aliases": 0, "skipped": 0, "validation_errors": 0,
                "match_overrides": 0, "placement_overrides": 0, "override_file": None,
            },
        )
        rows = self.table_rows()
        self.assertEqual(
            rows["participants"],
            [("alpha", 1, 1), ("beta", 2, 2), ("delta", 4, 4), ("gamma", 3, 3)],
        )
        self.assertEqual(rows["matches"], self.EXPECTED_MATCHES)
        self.assertEqual(rows["tournament"], [("challonge", 1)])

    def test_v2_attribute_payloads_import_like_v1(self) -> None:
        def as_v2(items: list[dict], wrapper: str) -> dict:
            return {"data": [{"id": item[wrapper]["id"], "attributes": item[wrapper]} for item in items]}

        self.run_import(
            as_v2(participants_payload(), "participant"),
            as_v2(matches_payload(), "match"),
        )

        self.assertEqual(self.table_rows()["matches"], self.EXPECTED_MATCHES)

    def test_replace_removes_previous_rows(self) -> None:
        self.run_import()
        with sqlite3.connect(self.db_path) as connection, connection:
            connection.execute(
                "INSERT INTO matches (match_id, tournament_id, player_1_id, player_2_id) "
                "VALUES ('stale', ?, 'alpha', 'beta')",
                (TOURNAMENT_ID,),
            )
        result = self.run_import(replace=True)
        self.assertNotIn("stale", [row[0] for row in self.table_rows()["matches"]])

        # The backup written before replacing still holds the old rows.
        backup_path = result["backup_path"]
        self.assertEqual(backup_path.parent, self.db_path.parent)
        self.assertTrue(backup_path.name.startswith("import_before_import_wc_01_"))
        with closing(sqlite3.connect(backup_path)) as connection:
            stale = connection.execute(
                "SELECT COUNT(*) FROM matches WHERE match_id = 'stale'"
            ).fetchone()[0]
        self.assertEqual(stale, 1)

    def test_import_without_replace_writes_no_backup(self) -> None:
        self.run_import()

        self.assertEqual(
            sorted(self.db_path.parent.glob("import_before_*.db")), []
        )

    def test_unknown_alias_is_rejected_without_writing(self) -> None:
        participants = participants_payload()
        participants[0]["participant"]["name"] = "Nobody"
        with self.assertRaisesRegex(ValueError, "Unknown aliases found: Nobody"):
            self.run_import(participants)
        self.assertEqual(self.table_rows()["participants"], [])

    def test_unmapped_match_is_rejected(self) -> None:
        matches = matches_payload()
        matches[1]["match"]["player2_id"] = 999
        with self.assertRaisesRegex(ValueError, "Matches could not be mapped: 2"):
            self.run_import(matches=matches)

    def test_score_conflicting_with_winner_is_rejected(self) -> None:
        matches = matches_payload()
        matches[1]["match"]["scores_csv"] = "0-3"
        with self.assertRaisesRegex(ValueError, "Match 2: Score conflicts with winner"):
            self.run_import(matches=matches)

    def test_inconsistent_matches_are_reported_together(self) -> None:
        matches = matches_payload()
        matches[1]["match"]["player2_id"] = 101
        matches[2]["match"]["winner_id"] = None
        with self.assertRaises(ValueError) as raised:
            self.run_import(matches=matches)
        message = str(raised.exception)
        self.assertIn("Match 2: Player is matched against themselves", message)
        self.assertIn("Match 3: Completed match without a winner", message)

    def test_unexpected_payload_shape_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unerwartetes Challonge-JSON-Format"):
            self.run_import({"participants": []})

    def test_unknown_internal_tournament_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown internal tournament ID: wc_99"):
            challonge_import.import_payloads("wc_99", participants_payload(), matches_payload())

    def test_save_raw_writes_payloads_to_raw_directory(self) -> None:
        participants_path, matches_path = challonge_import.save_raw(
            TOURNAMENT_ID, participants_payload(), matches_payload()
        )
        self.assertEqual(participants_path, self.raw_dir / TOURNAMENT_ID / "participants.json")
        self.assertEqual(json.loads(matches_path.read_text(encoding="utf-8")), matches_payload())


class OverrideTests(ChallongeImportTestCase):
    """Corrections from data/overrides/<tournament>.json (temporary here)."""

    def test_placement_and_match_overrides_are_applied(self) -> None:
        override_path = self.write_override({
            "placements": {"Alpha Old": 2, "Beta": 1},
            "matches": {
                "C": {"winner": "Delta", "score": "1-2"},
                "2": {"score": "3-1"},
            },
        })

        result = self.run_import()

        rows = self.table_rows()
        self.assertEqual(
            rows["participants"],
            [("alpha", 2, 1), ("beta", 1, 2), ("delta", 4, 4), ("gamma", 3, 3)],
        )
        matches = {row[0]: row for row in rows["matches"]}
        self.assertEqual(matches["wc_01_challonge_3"][5:9], ("delta", 1, 2, 1))
        self.assertEqual(matches["wc_01_challonge_2"][5:9], ("alpha", 3, 1, 1))
        self.assertEqual(result["match_overrides"], 2)
        self.assertEqual(result["placement_overrides"], 2)
        self.assertEqual(result["override_file"], str(override_path))

    def test_override_can_clear_a_winner(self) -> None:
        matches = matches_payload()
        matches[3]["match"]["state"] = "open"
        self.write_override({"matches": {"D": {"winner": None}}})

        self.run_import(matches=matches)

        match = {row[0]: row for row in self.table_rows()["matches"]}["wc_01_challonge_4"]
        self.assertIsNone(match[5])

    def test_invalid_override_files_are_rejected(self) -> None:
        cases = (
            ([], "Override file must contain a JSON object"),
            ({"placements": []}, "Override field 'placements' must be a JSON object"),
            ({"matches": []}, "Override field 'matches' must be a JSON object"),
            ({"placements": {"Nobody": 1}}, "Unknown player in placement override: Nobody"),
            ({"placements": {"Beta": "first"}}, "Invalid placement for Beta: 'first'"),
            ({"matches": {"A": "bad"}}, "Match override for A must be a JSON object"),
            ({"matches": {"A": {"winner": "Nobody"}}}, "Unknown winner in override for match A: Nobody"),
        )
        for payload, message in cases:
            with self.subTest(message=message):
                self.write_override(payload)
                with self.assertRaisesRegex(ValueError, message):
                    self.run_import()


class CommandLineTests(ChallongeImportTestCase):
    """`--from-files` imports and the printed summary."""

    SUMMARY = (
        "\nWC_01 imported successfully\n"
        "Participants:       4\n"
        "Matches:          4\n"
        "  Group stage:   1\n"
        "  Knockout stage:       3\n"
        "Known scores:   2\n"
        "unknown scores: 2\n"
        "Unknown aliases:   0\n"
        "Errors:           0\n"
    )

    def run_cli(self, *arguments: str) -> str:
        challonge_import.save_raw(TOURNAMENT_ID, participants_payload(), matches_payload())
        output = StringIO()
        with (
            patch.object(sys, "argv", ["challonge_import.py", TOURNAMENT_ID, *arguments]),
            redirect_stdout(output),
        ):
            challonge_import.main()
        return output.getvalue()

    def test_from_files_prints_summary(self) -> None:
        output = self.run_cli("--from-files", "--replace")
        lines = output.splitlines(keepends=True)

        self.assertRegex(lines[2], r"^Backup: +\S+import_before_import_wc_01_")
        self.assertEqual("".join(lines[:2] + lines[3:]), self.SUMMARY)

    def test_override_summary_lists_applied_corrections(self) -> None:
        self.write_override({"placements": {"Beta": 1}, "matches": {"B": {"score": "3-1"}}})

        self.assertEqual(
            self.run_cli("--from-files"),
            self.SUMMARY
            + "Overrides applied:\n"
            + "  Matches:        1\n"
            + "  Placements:  1\n",
        )

    def test_challonge_id_is_required_without_files(self) -> None:
        with (
            patch.object(sys, "argv", ["challonge_import.py", TOURNAMENT_ID]),
            redirect_stdout(StringIO()),
            patch("sys.stderr", StringIO()),
            self.assertRaises(SystemExit),
        ):
            challonge_import.main()


class ParseScoreTests(unittest.TestCase):
    def test_score_formats(self) -> None:
        parse = challonge_import.parse_score
        Parsed = challonge_import.ParsedScore
        cases = (
            (("2-1", True), Parsed(2, 1, True)),
            (("3 – 0", True), Parsed(3, 0, True)),
            (("1:2", False), Parsed(1, 2, True)),
            (([2, 0], True), Parsed(2, 0, True)),
            (("0-0", True), Parsed(None, None, False)),
            (("0-0", False), Parsed(0, 0, True)),
            (("-1-2", True), Parsed(None, None, False)),
            (("2-1,1-2", True), Parsed(None, None, False)),
            ((None, True), Parsed(None, None, False)),
            ((["x", 1], True), Parsed(None, None, False)),
        )
        for (raw, winner_present), expected in cases:
            with self.subTest(raw=raw, winner_present=winner_present):
                self.assertEqual(parse(raw, winner_present), expected)


if __name__ == "__main__":
    unittest.main()
