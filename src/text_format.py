"""Small text formatting helpers shared by dashboard pages and narratives."""

from __future__ import annotations


def format_ordinal(value: int) -> str:
    """Format an integer as an English ordinal (1st, 2nd, 11th, 23rd)."""

    if 10 <= value % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"


ELO_MINUS = "−"


def format_elo(value: float) -> str:
    """Format an Elo rating or an unsigned Elo difference (one decimal)."""

    return f"{float(value):.1f}"


def format_elo_change(value: float) -> str:
    """Format a signed Elo change with one decimal and a typographic minus.

    Values that round to zero are shown as +0.0.
    """

    rounded = round(float(value), 1)
    sign = ELO_MINUS if rounded < 0 else "+"
    return f"{sign}{abs(rounded):.1f}"
