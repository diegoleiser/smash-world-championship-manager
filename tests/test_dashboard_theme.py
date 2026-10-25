"""Contrast and shared-component coverage for the light/dark color palette."""

import re
import unittest
from pathlib import Path

from dashboard_pages.theme import dashboard_theme_css
from dashboard_pages.ui_components import (
    archived_match_result_html, compact_metric_strip_html,
    compact_score_input_styles, dashboard_table_html,
)


def luminance(color):
    values = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    values = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in values]
    return sum(v * weight for v, weight in zip(values, (.2126, .7152, .0722)))


def contrast(first, second):
    high, low = sorted((luminance(first), luminance(second)), reverse=True)
    return (high + .05) / (low + .05)


class DashboardThemeTests(unittest.TestCase):
    def test_light_text_and_status_colors_remain_readable(self):
        css = dashboard_theme_css()
        colors = dict(re.findall(r'(--swc-[\w-]+): light-dark\((#[\da-f]{6}),', css))
        for name, color in colors.items():
            if name in {'--swc-surface', '--swc-summary-bg'}:
                continue
            for background in ('#ffffff', colors['--swc-surface'], colors['--swc-summary-bg']):
                with self.subTest(token=name, background=background):
                    self.assertGreaterEqual(contrast(color, background), 4.5)

    def test_all_custom_component_color_tokens_are_defined(self):
        root = Path(__file__).resolve().parents[1]
        css = dashboard_theme_css()
        definitions = set(re.findall(r'(--swc-[\w-]+):', css))
        paths = [root / 'dashboard.py', *(root / 'src/dashboard_pages').glob('*.py')]
        references = set()
        for path in paths:
            references.update(re.findall(r'var\((--swc-[\w-]+)\)', path.read_text()))
        self.assertFalse(references - definitions)

    def test_shared_cards_and_score_inputs_use_active_theme(self):
        metrics = compact_metric_strip_html([('Sets', 10)])
        score = compact_score_input_styles('demo_score_')
        result = archived_match_result_html('Final', 'Alpha', 'Beta', '2–1', winner_name='Alpha', status_label='Played')
        for markup in (metrics, score, result):
            self.assertIn('var(--swc-text)', markup)
            self.assertNotIn('color: rgb(250', markup)
            self.assertNotIn('color:rgb(250', markup)
        self.assertIn('var(--swc-positive-bright)', result)

    def test_theme_palette_preserves_dark_summary_and_highlight(self):
        css = dashboard_theme_css()
        self.assertIn('light-dark(#eff6ff, rgba(28, 74, 112, 0.55))', css)
        self.assertIn('light-dark(#916000, #f2c94c)', css)
        self.assertNotIn('prefers-color-scheme', css)  # Follow app selection, not OS preference.
