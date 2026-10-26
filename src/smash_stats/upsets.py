"""Biggest Elo upsets: rated Set wins against a clearly higher-rated player."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from smash_stats.database import DEFAULT_DB_PATH
from smash_stats.elo_history import calculate_elo_history
from smash_stats.elo_rules import ELO_K_FACTOR


UPSET_MINIMUM_ELO_GAP = 150.0
UPSET_MINIMUM_PRIOR_SETS = 5


def find_upsets(
    history: list[dict[str, Any]],
    *,
    minimum_gap: float = UPSET_MINIMUM_ELO_GAP,
    minimum_prior_sets: int = UPSET_MINIMUM_PRIOR_SETS,
) -> list[dict[str, Any]]:
    """
    Returns upsets from a chronological Elo history, biggest gap first.

    An upset is a rated Set won by the player whose Elo before that Set was at
    least ``minimum_gap`` points lower. The winner needs ``minimum_prior_sets``
    rated Sets before it, so wins of newcomers whose rating is still settling
    near the 1000 starting value do not count. Ties keep chronological order.
    """

    prior_sets: Counter[str] = Counter()
    upsets: list[dict[str, Any]] = []

    for event in history:
        winner_id = str(event["winner_id"])
        loser_id = str(event["loser_id"])
        winner_before = float(event["winner_rating_before"])
        loser_before = float(event["loser_rating_before"])
        gap = loser_before - winner_before

        if gap >= minimum_gap and prior_sets[winner_id] >= minimum_prior_sets:
            upsets.append(
                {
                    "rank": 0,
                    "sequence": event["sequence"],
                    "match_id": event["match_id"],
                    "tournament_id": event["tournament_id"],
                    "tournament_number": event["tournament_number"],
                    "tournament_date": event["tournament_date"],
                    "stage": event["stage"],
                    "round_label": event["round_label"],
                    "winner_id": winner_id,
                    "winner": event["winner"],
                    "loser_id": loser_id,
                    "loser": event["loser"],
                    "winner_elo_before": round(winner_before, 1),
                    "loser_elo_before": round(loser_before, 1),
                    "elo_gap": round(gap, 1),
                    "elo_gain": round(float(event["rating_change"]), 1),
                    "winner_score": event["winner_score"],
                    "loser_score": event["loser_score"],
                    "score_known": bool(event["score_known"]),
                }
            )

        prior_sets[winner_id] += 1
        prior_sets[loser_id] += 1

    upsets.sort(key=lambda upset: (-upset["elo_gap"], upset["sequence"]))
    for rank, upset in enumerate(upsets, start=1):
        upset["rank"] = rank

    return upsets


def get_upsets(
    db_path: str | Path = DEFAULT_DB_PATH,
    *,
    limit: int | None = None,
    k_factor: float = ELO_K_FACTOR,
    minimum_gap: float = UPSET_MINIMUM_ELO_GAP,
    minimum_prior_sets: int = UPSET_MINIMUM_PRIOR_SETS,
) -> list[dict[str, Any]]:
    """Returns the archive's upsets, biggest Elo gap first."""

    if limit is not None and limit <= 0:
        raise ValueError("limit must be greater than zero.")

    upsets = find_upsets(
        calculate_elo_history(db_path, k_factor=k_factor),
        minimum_gap=minimum_gap,
        minimum_prior_sets=minimum_prior_sets,
    )
    return upsets if limit is None else upsets[:limit]
