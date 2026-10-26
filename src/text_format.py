"""Small text formatting helpers shared by dashboard pages and narratives."""

from __future__ import annotations


def format_ordinal(value: int) -> str:
    """Format an integer as an English ordinal (1st, 2nd, 11th, 23rd)."""

    if 10 <= value % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"
