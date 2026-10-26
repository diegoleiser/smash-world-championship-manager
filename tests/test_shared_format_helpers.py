"""Shared formatting helpers that replaced duplicated page and narrative code."""

import unittest

from bracket_visualization import match_status_label
from dashboard_pages.ui_components import selector_card_styles, versus_header_html
from text_format import format_ordinal


class OrdinalTests(unittest.TestCase):
    def test_suffixes_including_teens(self):
        cases = {
            1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 10: "10th",
            11: "11th", 12: "12th", 13: "13th", 20: "20th", 21: "21st",
            22: "22nd", 23: "23rd", 101: "101st", 111: "111th", 112: "112th",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(format_ordinal(value), expected)


class MatchStatusLabelTests(unittest.TestCase):
    def test_known_and_unknown_statuses(self):
        cases = {
            "waiting": "Waiting",
            "pending": "Ready",
            "completed": "Played",
            "forfeit": "W–L",
            "bye": "Bye",
            "cancelled": "Cancelled",
            "inactive": "Inactive",
            "in_progress": "In_Progress",
        }
        for status, expected in cases.items():
            with self.subTest(status=status):
                self.assertEqual(match_status_label(status), expected)


class VersusHeaderTests(unittest.TestCase):
    def test_markup_matches_previous_inline_heading(self):
        self.assertEqual(
            versus_header_html(
                "Alpha & Co",
                "<Beta>",
                name_size="1.6rem",
                margin="0.5rem 0 1.25rem 0",
            ),
            '<div style="display:grid;grid-template-columns:1fr auto 1fr;'
            'align-items:center;gap:1rem;margin:0.5rem 0 1.25rem 0;">'
            '<div style="text-align:right;font-size:1.6rem;font-weight:750;">'
            'Alpha &amp; Co</div>'
            '<div style="opacity:0.55;font-size:0.9rem;font-weight:700;">VS</div>'
            '<div style="text-align:left;font-size:1.6rem;font-weight:750;">'
            '&lt;Beta&gt;</div>'
            '</div>',
        )


class SelectorCardStylesTests(unittest.TestCase):
    def test_pages_share_one_card_language(self):
        player = selector_card_styles("player_profile_selector", "1.4rem")
        tournament = selector_card_styles("archived_tournament_selector", "1.75rem")

        self.assertEqual(
            player.replace("player_profile_selector", "KEY").replace("1.4rem", "SIZE"),
            tournament.replace("archived_tournament_selector", "KEY").replace("1.75rem", "SIZE"),
        )
        self.assertEqual(player.count('div[class*="st-key-player_profile_selector"]'), 10)
        self.assertIn("font-size: 1.4rem !important;", player)
        for leftover in ("{{", "}}", "{container_key}", "{value_font_size}"):
            self.assertNotIn(leftover, player)


if __name__ == "__main__":
    unittest.main()
