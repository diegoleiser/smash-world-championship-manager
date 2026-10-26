"""Regression tests for small dashboard fixes (group set order, defaults)."""

import unittest

from dashboard_pages.forecast_format import default_participant_ids
from tournament.archived_bracket import sort_group_matches_by_round


def _match(label, name):
    return {"round_label": label, "name": name}


class GroupSetOrderTests(unittest.TestCase):
    def test_sorts_by_round_and_keeps_order_within_round(self):
        matches = [
            _match("Group A · Round 6", "a"),
            _match("Group A · Round 1", "b"),
            _match("Group A · Round 2", "c"),
            _match("Group A · Round 1", "d"),
        ]
        ordered = [m["name"] for m in sort_group_matches_by_round(matches)]
        self.assertEqual(ordered, ["b", "d", "c", "a"])

    def test_groups_stay_together(self):
        matches = [
            _match("Group B · Round 1", "b1"),
            _match("Group A · Round 2", "a2"),
            _match("Group A · Round 1", "a1"),
        ]
        ordered = [m["name"] for m in sort_group_matches_by_round(matches)]
        self.assertEqual(ordered, ["a1", "a2", "b1"])

    def test_unparseable_labels_keep_original_order(self):
        matches = [
            _match("Round 2", "x"),
            _match(None, "y"),
            _match("Round 1", "z"),
        ]
        ordered = [m["name"] for m in sort_group_matches_by_round(matches)]
        self.assertEqual(ordered, ["x", "y", "z"])

    def test_plain_numeric_labels_from_imports_are_sorted(self):
        matches = [_match("3", "c"), _match("1", "a"), _match("2", "b")]
        ordered = [m["name"] for m in sort_group_matches_by_round(matches)]
        self.assertEqual(ordered, ["a", "b", "c"])

    def test_does_not_mutate_input(self):
        matches = [_match("Round 2", "x"), _match("Round 1", "y")]
        sort_group_matches_by_round(matches)
        self.assertEqual([m["name"] for m in matches], ["x", "y"])


class MonteCarloDefaultsTests(unittest.TestCase):
    def test_includes_all_active_players_sorted_by_elo(self):
        players = [
            {"player_id": "1", "display_name": "Low", "active": 1, "core_player": 1},
            {"player_id": "2", "display_name": "Debut", "active": 1, "core_player": 0},
            {"player_id": "3", "display_name": "Gone", "active": 0, "core_player": 1},
            {"player_id": "4", "display_name": "Top", "active": 1, "core_player": 1},
        ]
        elo = {"1": 900.0, "2": 1000.0, "3": 1200.0, "4": 1100.0}
        self.assertEqual(default_participant_ids(players, elo), ["4", "2", "1"])

    def test_caps_at_maximum_field_size(self):
        players = [
            {"player_id": str(i), "display_name": f"P{i}", "active": 1}
            for i in range(40)
        ]
        self.assertEqual(len(default_participant_ids(players, {})), 32)


if __name__ == "__main__":
    unittest.main()
