"""Render every dashboard page against synthetic demo data only.

The dashboard resolves its database relative to ``dashboard.py``. Each run
therefore uses a copy of the script in a temporary project whose ``src``
links to the repository and whose ``data`` holds a freshly generated demo
database. The private ``data/smash_wm.db`` is never opened.
"""

from __future__ import annotations

import shutil
import sqlite3
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = PROJECT_ROOT / "examples"
SRC_DIR = PROJECT_ROOT / "src"
for path in (EXAMPLES_DIR, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # pragma: no cover - dashboard dependencies missing
    AppTest = None

from create_demo_database import create_demo_database  # noqa: E402
import tournament_manager as tournament  # noqa: E402
from smash_stats.upsets import get_upsets  # noqa: E402


GROUP_DRAFT_NUMBER = 6
UPSET_TOURNAMENT_NUMBER = 7
GROUP_PLAYERS = ("atlas", "blaze", "comet", "drift", "echo", "flux")
PAGE_TITLES = {
    "": "🎮 Smash World Championship",
    "Players": "👤 Player profile",
    "Matchups": "🤝 Matchups",
    "Tournaments": "🏆 Tournaments",
    "Hall of Fame": "🏛️ Hall of Fame",
    "Tournament Manager": "🛠 Tournament Manager",
    "Monte Carlo": "Monte Carlo",
}


def _add_upset_tournament(db_path: Path) -> None:
    """Archive a synthetic event in which Halo upsets Atlas after six losses."""

    with sqlite3.connect(db_path) as connection, connection:
        connection.execute(
            """
            INSERT INTO tournaments (
                tournament_id, tournament_number, tournament_date, winner_id,
                bracket_source, match_data_available
            )
            VALUES ('wc_07_upset', ?, '2027-01-15', 'halo', 'manual', 1)
            """,
            (UPSET_TOURNAMENT_NUMBER,),
        )
        connection.executemany(
            "INSERT INTO tournament_participants (tournament_id, player_id, placement, seed) "
            "VALUES ('wc_07_upset', ?, ?, ?)",
            [("halo", 1, 2), ("atlas", 2, 1)],
        )
        connection.executemany(
            """
            INSERT INTO matches (
                match_id, tournament_id, player_1_id, player_2_id, winner_id,
                player_1_score, player_2_score, score_known, stage, round_label,
                suggested_play_order
            )
            VALUES (?, 'wc_07_upset', 'atlas', 'halo', ?, ?, ?, 1, ?, ?, ?)
            """,
            [
                (f"wc_07_upset_{index}", "atlas", 2, 0, "group_stage", "1", index)
                for index in range(6)
            ]
            + [("wc_07_upset_final", "halo", 1, 3, "knockout", "GF", 6)],
        )


def _create_group_stage_draft(db_path: Path) -> str:
    """Add a single-group draft with one completed Set to the demo data."""

    draft_id = tournament.create_draft(
        db_path,
        tournament_number=GROUP_DRAFT_NUMBER,
        tournament_date="2026-10-10",
        format_type=tournament.FORMAT_GROUP_STAGE,
        bracket_entry_mode=tournament.ENTRY_SPLIT_BY_GROUP_SEED,
    )
    for seed, player_id in enumerate(GROUP_PLAYERS, start=1):
        tournament.add_participant(
            db_path,
            draft_id,
            player_id,
            manual_seed=seed,
        )
    tournament.create_draft_groups(db_path, draft_id, 1)
    tournament.create_draft_group_matches(db_path, draft_id)
    first_match = tournament.get_draft_group_matches(db_path, draft_id)[0]
    tournament.update_draft_group_match(
        db_path,
        str(first_match["group_match_id"]),
        status="completed",
        player_1_score=2,
        player_2_score=1,
    )
    return draft_id


@unittest.skipIf(AppTest is None, "Streamlit dashboard dependencies missing")
class DashboardSmokeTests(unittest.TestCase):
    """Every page and Tournament Manager state renders without exceptions."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary_directory = tempfile.TemporaryDirectory()
        project = Path(cls.temporary_directory.name)
        shutil.copy(PROJECT_ROOT / "dashboard.py", project / "dashboard.py")
        (project / "src").symlink_to(SRC_DIR, target_is_directory=True)
        data_dir = project / "data"
        data_dir.mkdir()
        db_path = data_dir / "smash_wm.db"
        with redirect_stdout(StringIO()):
            create_demo_database(
                db_path,
                data_dir / "model_artifacts" / "combined_v0.2",
            )
        cls.group_draft_id = _create_group_stage_draft(db_path)
        _add_upset_tournament(db_path)
        cls.upsets = get_upsets(db_path)
        cls.bracket_draft_id = next(
            str(draft["draft_id"])
            for draft in tournament.list_drafts(db_path)
            if int(draft["tournament_number"]) == 5
        )
        cls.script_path = project / "dashboard.py"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary_directory.cleanup()

    def run_app(self, **query_params: str) -> AppTest:
        app = AppTest.from_file(str(self.script_path), default_timeout=60)
        for key, value in query_params.items():
            app.query_params[key] = value
        app.run()
        self.assert_no_exception(app)
        return app

    def assert_no_exception(self, app: AppTest) -> None:
        self.assertEqual(
            [exception.value for exception in app.exception],
            [],
        )

    def select_draft(self, app: AppTest, tournament_number: int) -> None:
        selector = next(
            box for box in app.selectbox if box.label == "Select draft"
        )
        label = next(
            option
            for option in selector.options
            if option.startswith(f"WC {tournament_number:02d} ")
        )
        selector.set_value(label).run()
        self.assert_no_exception(app)

    def test_every_page_renders(self) -> None:
        for page, title in PAGE_TITLES.items():
            with self.subTest(page=page or "Home"):
                app = self.run_app(**({"page": page} if page else {}))
                self.assertIn(title, [element.value for element in app.title])

    def test_player_and_tournament_detail_links_render(self) -> None:
        for page, params in (
            ("Players", {"player_id": "atlas"}),
            ("Tournaments", {"tournament": "1"}),
        ):
            with self.subTest(page=page):
                app = self.run_app(page=page, **params)
                self.assertIn(
                    PAGE_TITLES[page],
                    [element.value for element in app.title],
                )

    def test_synthetic_archive_contains_the_halo_upset(self) -> None:
        self.assertIn(
            ("halo", "atlas", UPSET_TOURNAMENT_NUMBER),
            [
                (upset["winner_id"], upset["loser_id"], upset["tournament_number"])
                for upset in self.upsets
            ],
        )

    def test_upsets_render_on_home_player_and_tournament_pages(self) -> None:
        home = self.run_app()
        self.assertIn("Biggest Upsets", [element.value for element in home.subheader])
        upset_tables = [
            element.value
            for element in home.markdown
            if element.value.startswith('<div class="control-table-scroll">')
            and 'data-label="Elo Gap"' in element.value
        ]
        self.assertTrue(upset_tables)
        self.assertIn("/players?player_id=halo", upset_tables[0])
        self.assertEqual(len(upset_tables), 1)
        self.assertEqual(
            "Show all" in upset_tables[0],
            len(self.upsets) > 5,
        )
        self.assertNotIn("upsets", [element.label for element in home.expander])

        player = self.run_app(page="Players", player_id="halo")
        self.assertTrue(
            any("BIGGEST UPSET WIN" in element.value for element in player.markdown)
        )

        archive = self.run_app(page="Tournaments", tournament=str(UPSET_TOURNAMENT_NUMBER))
        self.assertIn("Upsets", [element.value for element in archive.subheader])

        without_upset = self.run_app(page="Tournaments", tournament="1")
        self.assertNotIn("Upsets", [element.value for element in without_upset.subheader])

    def test_hall_of_fame_shows_record_groups_and_recent_milestones(self) -> None:
        app = self.run_app(page="Hall of Fame")
        subheaders = [element.value for element in app.subheader]

        for group in ("Championships", "Performance", "Elo Ranking", "Rivalries"):
            self.assertIn(group, subheaders)
        self.assertIn("Recent Milestones", subheaders)
        card_grids = [
            element.value
            for element in app.markdown
            if element.value.startswith('<div class="hof-grid">')
        ]
        self.assertEqual(len(card_grids), 4)
        self.assertIn('<header class="hof-card-title">Most Titles</header>', card_grids[0])
        self.assertIn("/players?player_id=", card_grids[0])
        self.assertNotIn("Losing Streak", "".join(card_grids))

    def test_table_styles_are_loaded_once_per_page(self) -> None:
        app = self.run_app()
        markdown = [element.value for element in app.markdown]
        style_blocks = [
            value for value in markdown if ".control-table-header {" in value
        ]

        # st.markdown dedents its body; mixing differently indented style
        # sheets in one call turns the table styles into a code block.
        self.assertEqual(len(style_blocks), 1)
        self.assertTrue(textwrap.dedent(style_blocks[0]).strip().startswith("<style>"))
        self.assertNotIn(".stApp {", style_blocks[0])
        summary_style_blocks = [value for value in markdown if ".dash-summary {" in value]
        self.assertEqual(len(summary_style_blocks), 1)
        self.assertTrue(
            textwrap.dedent(summary_style_blocks[0]).strip().startswith("<style>")
        )
        self.assertGreater(
            sum('class="control-table-scroll"' in value for value in markdown),
            1,
        )

    def test_matchup_comparison_renders_for_selected_matrix_cell(self) -> None:
        app = self.run_app(page="Matchups")
        app.session_state["matchups_matrix_selection"] = {
            "selection": {"rows": [], "columns": [], "cells": [[0, "Blaze"]]},
        }
        app.run()
        self.assert_no_exception(app)
        self.assertIn(
            "Head-to-Head Details",
            [element.value for element in app.subheader],
        )

    def test_tournament_manager_draft_states_render(self) -> None:
        for tournament_number, draft_id in (
            (5, self.bracket_draft_id),
            (GROUP_DRAFT_NUMBER, self.group_draft_id),
        ):
            for detailed in (False, True):
                with self.subTest(
                    tournament=tournament_number,
                    detailed_management=detailed,
                ):
                    app = self.run_app(page="Tournament Manager")
                    self.select_draft(app, tournament_number)
                    self.assertIn(
                        "## Tournament Control Center",
                        [element.value for element in app.markdown],
                    )
                    if detailed:
                        app.toggle(
                            key=f"show_detailed_management_{draft_id}"
                        ).set_value(True).run()
                        self.assert_no_exception(app)


if __name__ == "__main__":
    unittest.main()
