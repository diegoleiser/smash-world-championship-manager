"""Pure presentation helpers for the biggest Elo upsets."""

from __future__ import annotations

import html
from typing import Any

from dashboard_pages.navigation_routes import (
    player_profile_url,
    tournament_archive_url,
)
from dashboard_pages.ui_components import internal_dashboard_link
from smash_stats.upsets import UPSET_MINIMUM_ELO_GAP, UPSET_MINIMUM_PRIOR_SETS


UPSET_CAPTION = (
    f"Wins against a player rated at least {UPSET_MINIMUM_ELO_GAP:.0f} Elo "
    "higher before the Set. Winners need "
    f"{UPSET_MINIMUM_PRIOR_SETS} rated Sets before."
)


def upset_phase_label(stage: str | None) -> str:
    """Return one label for Challonge and internal stage names."""

    if stage in {"group", "group_stage"}:
        return "Group Stage"
    if stage in {"knockout", "bracket"}:
        return "Bracket"
    return str(stage).replace("_", " ").title() if stage else "–"


def upset_score_text(upset: dict[str, Any]) -> str:
    """Return the winner's score first, or a dash for unknown scores."""

    if upset["winner_score"] is None or upset["loser_score"] is None:
        return "–"
    return f"{upset['winner_score']}–{upset['loser_score']}"


def upset_elo_before_text(upset: dict[str, Any]) -> str:
    """Return winner and loser Elo before the Set, winner first."""

    return (
        f"{float(upset['winner_elo_before']):.1f} vs "
        f"{float(upset['loser_elo_before']):.1f}"
    )


def top_upsets_by_pairing(
    upsets: list[dict[str, Any]],
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Return the biggest upsets with at most one entry per pairing."""

    seen_pairings: set[frozenset[str]] = set()
    selected = []
    for upset in upsets:
        pairing = frozenset((str(upset["winner_id"]), str(upset["loser_id"])))
        if pairing in seen_pairings:
            continue
        seen_pairings.add(pairing)
        selected.append(upset)
        if len(selected) == limit:
            break
    return selected


def upsets_with_top_first(
    upsets: list[dict[str, Any]],
    limit: int = 5,
) -> tuple[list[dict[str, Any]], int]:
    """Return the top list (one per pairing) followed by all other upsets.

    The second value is the length of the top list.
    """

    top = top_upsets_by_pairing(upsets, limit)
    top_ids = {id(upset) for upset in top}
    return top + [upset for upset in upsets if id(upset) not in top_ids], len(top)


def upset_set_html(upset: dict[str, Any]) -> str:
    """Return "Winner vs Loser" with the winner in bold."""

    winner_link = internal_dashboard_link(
        str(upset["winner"]),
        player_profile_url(str(upset["winner_id"])),
    )
    loser_link = internal_dashboard_link(
        str(upset["loser"]),
        player_profile_url(str(upset["loser_id"])),
    )
    return (
        "<span>"
        '<span class="control-table-nowrap">'
        f'<span class="control-table-strong">{winner_link}</span>'
        ' <span class="control-table-muted">vs</span> '
        f'<span class="control-table-regular">{loser_link}</span>'
        "</span>"
        "</span>"
    )


def upset_gap_html(upset: dict[str, Any]) -> str:
    """Return the Elo gap with both Elo ratings before the Set below it."""

    return (
        "<span>"
        f"+{float(upset['elo_gap']):.1f}"
        '<span class="control-table-subline">'
        f"{upset_elo_before_text(upset)}"
        "</span>"
        "</span>"
    )


def upset_table(
    upsets: list[dict[str, Any]],
    *,
    include_tournament: bool = True,
) -> dict[str, Any]:
    """Return headers, rows, markup and columns for dashboard_table_html.

    Columns: the Set (winner in bold), the tournament with its phase (or
    only the phase), the Elo gap with both Elo ratings before the Set, and the
    score.
    """

    place_header = "Tournament" if include_tournament else "Phase"
    headers = ["Set", place_header, "Elo Gap", "Score"]
    columns = (
        "minmax(14rem,2.2fr) minmax(9rem,1.2fr) "
        "minmax(6.5rem,0.8fr) minmax(4.5rem,0.6fr)"
    )

    rows = []
    markup: dict[tuple[int, int], str] = {}
    for row_index, upset in enumerate(upsets):
        phase = upset_phase_label(upset["stage"])
        place_text = phase
        if include_tournament:
            tournament_label = f"WC {int(upset['tournament_number']):02d}"
            place_text = f"{tournament_label} · {phase}"
            markup[(row_index, 1)] = (
                "<span>"
                + internal_dashboard_link(
                    tournament_label,
                    tournament_archive_url(int(upset["tournament_number"])),
                )
                + f" · {html.escape(phase)}</span>"
            )
        rows.append(
            [
                f"{upset['winner']} vs {upset['loser']}",
                place_text,
                f"+{float(upset['elo_gap']):.1f}",
                upset_score_text(upset),
            ]
        )
        markup[(row_index, 0)] = upset_set_html(upset)
        markup[(row_index, 2)] = upset_gap_html(upset)

    return {
        "headers": headers,
        "rows": rows,
        "cell_html": markup,
        "columns": columns,
    }


def player_upset_wins(
    upsets: list[dict[str, Any]],
    player_id: str,
) -> list[dict[str, Any]]:
    """Return a player's upset wins, biggest gap first."""

    return [upset for upset in upsets if str(upset["winner_id"]) == str(player_id)]


def tournament_upsets(
    upsets: list[dict[str, Any]],
    tournament_number: int,
) -> list[dict[str, Any]]:
    """Return one tournament's upsets, biggest gap first."""

    return [
        upset
        for upset in upsets
        if int(upset["tournament_number"]) == int(tournament_number)
    ]
