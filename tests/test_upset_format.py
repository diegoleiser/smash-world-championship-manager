"""Presentation helpers for the biggest Elo upsets."""

import unittest

from dashboard_pages.upset_format import (
    UPSET_CAPTION,
    upset_elo_before_text,
    player_upset_wins,
    top_upsets_by_pairing,
    tournament_upsets,
    upset_phase_label,
    upset_score_text,
    upset_table,
    upsets_with_top_first,
)


def upset(winner, loser, gap, *, tournament=12, stage="group", score=(2, 0)):
    return {
        "winner_id": winner, "winner": winner.title(),
        "loser_id": loser, "loser": loser.title(),
        "tournament_number": tournament, "stage": stage, "elo_gap": gap,
        "winner_elo_before": 1000.0, "loser_elo_before": 1000.0 + gap,
        "winner_score": score[0] if score else None,
        "loser_score": score[1] if score else None,
    }


class UpsetFormatTests(unittest.TestCase):
    def test_phase_labels_unify_challonge_and_internal_names(self):
        cases = {
            "group": "Group Stage", "group_stage": "Group Stage",
            "knockout": "Bracket", "bracket": "Bracket",
            "grand_final": "Grand Final", None: "–",
        }
        for stage, expected in cases.items():
            with self.subTest(stage=stage):
                self.assertEqual(upset_phase_label(stage), expected)

    def test_score_shows_winner_first_or_dash(self):
        self.assertEqual(upset_score_text(upset("a", "b", 120, score=(3, 2))), "3–2")
        self.assertEqual(upset_score_text(upset("a", "b", 120, score=None)), "–")

    def test_elo_before_lists_winner_first(self):
        self.assertEqual(
            upset_elo_before_text({"winner_elo_before": 1050.34, "loser_elo_before": 1372.56}),
            "1050.3 vs 1372.6",
        )

    def test_top_list_keeps_one_entry_per_pairing_in_either_direction(self):
        upsets = [
            upset("alpha", "beta", 310.0),
            upset("gamma", "delta", 290.0),
            upset("alpha", "beta", 270.0),
            upset("beta", "alpha", 230.0),
            upset("alpha", "epsilon", 240.0),
            upset("zeta", "eta", 220.0),
            upset("delta", "epsilon", 180.0),
            upset("zeta", "epsilon", 150.0),
        ]

        top = top_upsets_by_pairing(upsets)

        self.assertEqual(
            [(u["winner_id"], u["loser_id"], u["elo_gap"]) for u in top],
            [
                ("alpha", "beta", 310.0),
                ("gamma", "delta", 290.0),
                ("alpha", "epsilon", 240.0),
                ("zeta", "eta", 220.0),
                ("delta", "epsilon", 180.0),
            ],
        )
        self.assertEqual(len(top_upsets_by_pairing(upsets, limit=2)), 2)
        self.assertEqual(top_upsets_by_pairing([]), [])

    def test_top_list_comes_first_without_repeating_entries(self):
        upsets = [
            upset("alpha", "beta", 300),
            upset("alpha", "beta", 250),
            upset("gamma", "delta", 200),
            upset("zeta", "eta", 150),
        ]

        ordered, top_count = upsets_with_top_first(upsets, limit=2)

        self.assertEqual(top_count, 2)
        self.assertEqual([u["elo_gap"] for u in ordered], [300, 200, 250, 150])
        self.assertEqual(upsets_with_top_first([]), ([], 0))

    def test_table_combines_set_and_tournament_columns(self):
        table = upset_table([upset("alpha", "beta", 312.34, tournament=7, stage="knockout")])

        self.assertEqual(table["headers"], ["Set", "Tournament", "Elo Gap", "Score"])
        self.assertEqual(table["rows"], [["Alpha vs Beta", "WC 07 · Bracket", "+312.3", "2–0"]])
        self.assertEqual(len(table["columns"].split()), 4)
        self.assertEqual(
            table["cell_html"][(0, 1)],
            '<span><a class="control-table-link" href="/tournaments?tournament=7" '
            'target="_self">WC 07</a> · Bracket</span>',
        )

    def test_set_markup_shows_only_names_with_the_winner_in_bold(self):
        markup = upset_table([upset("alpha", "beta", 310.0)])["cell_html"][(0, 0)]

        winner, loser = markup.split('<span class="control-table-muted">vs</span>')
        self.assertIn('<span class="control-table-strong">', winner)
        self.assertIn('href="/players?player_id=alpha"', winner)
        self.assertIn('<span class="control-table-regular">', loser)
        self.assertIn('href="/players?player_id=beta"', loser)
        self.assertNotIn("control-table-subline", markup)
        self.assertNotIn("1000", markup)

    def test_gap_markup_groups_the_elo_ratings_below_the_gap(self):
        markup = upset_table([upset("alpha", "beta", 312.34)])["cell_html"][(0, 2)]

        self.assertEqual(
            markup,
            '<span>+312.3<span class="control-table-subline">1000.0 vs 1312.3</span></span>',
        )

    def test_set_markup_escapes_names(self):
        markup = upset_table([upset("a<b", "c&d", 150)])["cell_html"][(0, 0)]

        self.assertIn("A&lt;B", markup)
        self.assertIn("C&amp;D", markup)
        self.assertNotIn("<b", markup.replace("<b>", ""))

    def test_table_without_tournament_shows_only_the_phase(self):
        table = upset_table([upset("alpha", "beta", 150)], include_tournament=False)

        self.assertEqual(table["headers"], ["Set", "Phase", "Elo Gap", "Score"])
        self.assertEqual(table["rows"], [["Alpha vs Beta", "Group Stage", "+150.0", "2–0"]])
        self.assertNotIn((0, 1), table["cell_html"])

    def test_player_and_tournament_filters_keep_order(self):
        upsets = [
            upset("alpha", "beta", 300, tournament=12),
            upset("delta", "alpha", 200, tournament=12),
            upset("alpha", "epsilon", 150, tournament=8),
        ]

        self.assertEqual([u["elo_gap"] for u in player_upset_wins(upsets, "alpha")], [300, 150])
        self.assertEqual(player_upset_wins(upsets, "nobody"), [])
        self.assertEqual([u["elo_gap"] for u in tournament_upsets(upsets, 12)], [300, 200])
        self.assertEqual(tournament_upsets(upsets, 99), [])

    def test_caption_names_both_thresholds(self):
        self.assertIn("at least 150 Elo higher", UPSET_CAPTION)
        self.assertIn("5 rated Sets", UPSET_CAPTION)


if __name__ == "__main__":
    unittest.main()
