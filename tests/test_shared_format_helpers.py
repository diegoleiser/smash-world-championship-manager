"""Shared formatting helpers that replaced duplicated page and narrative code."""

import unittest

from bracket_visualization import match_status_label
from dashboard_pages.player import _summary_pair_html
from dashboard_pages.ui_components import selector_card_styles, versus_header_html
from datetime import date, datetime

from text_format import format_date, format_elo, format_elo_change, format_ordinal


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


class DateFormatTests(unittest.TestCase):
    def test_dates_use_day_month_name_year(self):
        cases = {
            "2026-10-24": "24 Oct 2026",
            "2022-01-03 18:30:00": "03 Jan 2022",
            date(2025, 6, 15): "15 Jun 2025",
            datetime(2024, 3, 31, 12, 0): "31 Mar 2024",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(format_date(value), expected)

    def test_missing_or_invalid_dates_show_a_dash(self):
        for value in (None, "", "unknown"):
            with self.subTest(value=value):
                self.assertEqual(format_date(value), "–")


class EloFormatTests(unittest.TestCase):
    def test_elo_values_use_one_decimal(self):
        for value, expected in ((1128.94, "1128.9"), (1000, "1000.0"), (938.95, "939.0")):
            with self.subTest(value=value):
                self.assertEqual(format_elo(value), expected)

    def test_elo_changes_are_signed_with_a_typographic_minus(self):
        cases = {
            54.62: "+54.6",
            -12.5: "\u221212.5",
            0: "+0.0",
            -0.04: "+0.0",
            0.05: "+0.1",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(format_elo_change(value), expected)


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


class SummaryPairTests(unittest.TestCase):
    def test_first_card_is_highlighted_and_values_are_markup(self):
        markup = _summary_pair_html(
            "rank-summary",
            ("BEST CAREER RANK", "Highest historical position", "#2"),
            ("FIRST REACHED AT", "First tournament at this rank", "<a href='/x'>WC 03</a>"),
        )

        body = markup.split("</style>")[1]
        self.assertEqual(
            body,
            "<div class='rank-summary-grid'>"
            "<div class='rank-summary-card rank-summary-highlight'><div>"
            "<div class='rank-summary-label'>BEST CAREER RANK</div>"
            "<div class='rank-summary-detail'>Highest historical position</div>"
            "</div><div class='rank-summary-value'>#2</div></div>"
            "<div class='rank-summary-card'><div>"
            "<div class='rank-summary-label'>FIRST REACHED AT</div>"
            "<div class='rank-summary-detail'>First tournament at this rank</div>"
            "</div><div class='rank-summary-value'><a href='/x'>WC 03</a></div></div>"
            "</div>",
        )
        self.assertIn(".rank-summary-highlight .rank-summary-value {color:var(--swc-gold);}", markup)
        self.assertIn("@media (max-width:650px) {.rank-summary-grid {grid-template-columns:1fr;}}", markup)


if __name__ == "__main__":
    unittest.main()
