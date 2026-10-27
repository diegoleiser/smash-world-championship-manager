"""Regression tests for small dashboard fixes (group set order)."""

import unittest

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


if __name__ == "__main__":
    unittest.main()
