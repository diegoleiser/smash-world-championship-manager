"""Render player history edge cases using synthetic data only."""

import unittest
from unittest.mock import MagicMock, patch

from dashboard_pages.player import render_player_page


class PlayerHistoryRegressionTests(unittest.TestCase):
    def test_empty_single_and_multiple_history_points_render(self):
        for count in (0, 1, 3):
            with self.subTest(history_points=count):
                timeline = [
                    {
                        "tournament": f"WC {index + 1}",
                        "tournament_number": index + 1,
                        "tournament_date": f"2026-01-0{index + 1}",
                        "elo": 1000.0 + index * 10,
                        "rank": 2,
                        "played_in_tournament": index != 1,
                    }
                    for index in range(count)
                ]
                ui = MagicMock()
                ui.query_params = {}
                ui.session_state = {}
                ui.selectbox.return_value = "Demo Player"
                ui.tabs.return_value = [MagicMock() for _ in range(4)]
                ui.columns.side_effect = lambda spec, **kwargs: [
                    MagicMock() for _ in range(spec if isinstance(spec, int) else len(spec))
                ]
                with (
                    patch("dashboard_pages.player.st", ui),
                    patch("dashboard_pages.player.narratives.generate_player_summary", return_value="Demo summary."),
                ):
                    render_player_page(
                        False,
                        load_players=lambda _: [{"player_id": "demo", "display_name": "Demo Player", "active": True}],
                        load_player_profile=lambda _: {"player": "Demo Player", "peak_elo": 1100.0},
                        load_player_timeline=lambda *_: timeline,
                        load_player_history=lambda _: [],
                        load_player_insights=lambda _: {
                            "longest_win_streak": 0,
                            "longest_loss_streak": 0,
                            "best_elo_event": None,
                            "opponents": [],
                        },
                        load_elo_ranking=lambda _: [],
                        format_ordinal=str,
                    )
                charts = [call.args[0].to_dict() for call in ui.altair_chart.call_args_list]
                self.assertEqual(len(charts), 2 if count else 0)
                if count:
                    rendered = " ".join(call.args[0] for call in ui.markdown.call_args_list)
                    self.assertIn("1100.0", rendered)
                    self.assertIn("Highest rating after any rated set", rendered)
                    self.assertIn("TOURNAMENT-END PEAK", rendered)
                    self.assertIn("Highest rating at tournament end", rendered)
                    self.assertIn(f"{max(row['elo'] for row in timeline):.1f}", rendered)
                    self.assertTrue(any("after individual sets" in call.args[0] for call in ui.caption.call_args_list))
                    for chart in charts:
                        datasets = list(chart["datasets"].values())
                        self.assertEqual(
                            {row["tournament"] for rows in datasets for row in rows if "tournament" in row},
                            {row["tournament"] for row in timeline},
                        )
                        segments = [row for rows in datasets for row in rows if "segment_type" in row]
                        self.assertEqual(len(segments), max(0, count - 1))
                        if count > 1:
                            self.assertEqual({row["segment_type"] for row in segments}, {"Played", "Did not participate"})


if __name__ == "__main__":
    unittest.main()
