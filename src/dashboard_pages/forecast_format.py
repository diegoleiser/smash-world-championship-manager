"""Presentation helpers for live tournament forecasts."""

from typing import Any

from monte_carlo.live_group import (
    LOSERS_LOCKED,
    SIDE_OPEN,
    WINNERS_LOCKED,
)


def format_winners_probability(
    probability: float,
    status: str,
) -> str:
    """Keep sampled extremes distinct from mathematically locked sides."""

    if status == WINNERS_LOCKED:
        return "100.0%"
    if status == LOSERS_LOCKED:
        return "0.0%"
    if status == SIDE_OPEN and probability >= 0.9995:
        return ">99.9%"
    if status == SIDE_OPEN and probability <= 0.0005:
        return "<0.1%"
    return f"{probability:.1%}"


MAX_PARTICIPANTS = 32


def default_participant_ids(
    players: list[dict[str, Any]],
    elo_by_player_id: dict[str, float],
) -> list[str]:
    """Preselect all active players, strongest Elo first."""

    active_ids = [
        str(player["player_id"])
        for player in players
        if int(player.get("active", 0)) == 1
    ]
    name_by_id = {
        str(player["player_id"]): str(player["display_name"])
        for player in players
    }
    return sorted(
        active_ids,
        key=lambda player_id: (
            -elo_by_player_id.get(player_id, 1000.0),
            name_by_id[player_id].casefold(),
        ),
    )[:MAX_PARTICIPANTS]
