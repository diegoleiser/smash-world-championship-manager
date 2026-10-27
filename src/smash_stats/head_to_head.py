"""Head-to-head statistics and terminal presentation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from smash_stats.common import _percentage
from smash_stats.database import DEFAULT_DB_PATH, connect_db, resolve_player


def get_head_to_head(
    player_a_reference: str,
    player_b_reference: str,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    """
    Calculates the head-to-head record between two players.

    Unknown scores count toward the match record when a winner is known, but not toward the game record.
    """

    with connect_db(db_path) as connection:
        player_a = resolve_player(connection, player_a_reference)
        player_b = resolve_player(connection, player_b_reference)

        player_a_id = player_a["player_id"]
        player_b_id = player_b["player_id"]

        if player_a_id == player_b_id:
            raise ValueError("A head-to-head comparison requires two different players.")

        matches = connection.execute(
            """
            SELECT
                m.match_id,
                m.tournament_id,
                t.tournament_number,
                t.tournament_date,
                m.stage,
                m.bracket_side,
                m.round_label,
                m.player_1_id,
                m.player_2_id,
                m.winner_id,
                m.player_1_score,
                m.player_2_score,
                m.score_known,
                m.walkover,
                m.completed_at,
                m.suggested_play_order
            FROM matches AS m
            JOIN tournaments AS t
              ON t.tournament_id = m.tournament_id
            WHERE
                (m.player_1_id = ? AND m.player_2_id = ?)
                OR
                (m.player_1_id = ? AND m.player_2_id = ?)
            ORDER BY
                t.tournament_date,
                t.tournament_number,
                CASE WHEN m.completed_at IS NULL THEN 1 ELSE 0 END,
                m.completed_at,
                CASE WHEN m.suggested_play_order IS NULL THEN 1 ELSE 0 END,
                m.suggested_play_order,
                m.match_id
            """,
            (
                player_a_id,
                player_b_id,
                player_b_id,
                player_a_id,
            ),
        ).fetchall()

    player_a_wins = 0
    player_b_wins = 0
    undecided_matches = 0
    player_a_games = 0
    player_b_games = 0
    matches_with_known_score = 0
    match_history: list[dict[str, Any]] = []

    for row in matches:
        if row["winner_id"] == player_a_id:
            player_a_wins += 1
        elif row["winner_id"] == player_b_id:
            player_b_wins += 1
        else:
            undecided_matches += 1

        score_known = bool(row["score_known"])
        score_a: int | None = None
        score_b: int | None = None

        player_1_score = row["player_1_score"]
        player_2_score = row["player_2_score"]

        if (
            score_known
            and player_1_score is not None
            and player_2_score is not None
            and not row["walkover"]
        ):
            if row["player_1_id"] == player_a_id:
                score_a = int(player_1_score)
                score_b = int(player_2_score)
            else:
                score_a = int(player_2_score)
                score_b = int(player_1_score)

            player_a_games += score_a
            player_b_games += score_b
            matches_with_known_score += 1

        winner_name = None
        if row["winner_id"] == player_a_id:
            winner_name = player_a["display_name"]
        elif row["winner_id"] == player_b_id:
            winner_name = player_b["display_name"]

        score_text = (
            f"{score_a}-{score_b}"
            if score_a is not None and score_b is not None
            else None
        )

        match_history.append(
            {
                "match_id": row["match_id"],
                "tournament_id": row["tournament_id"],
                "tournament": f"WC {row['tournament_number']:02d}",
                "tournament_number": row["tournament_number"],
                "date": row["tournament_date"],
                "stage": row["stage"],
                "bracket_side": row["bracket_side"],
                "round_label": row["round_label"],
                "winner": winner_name,
                "winner_id": row["winner_id"],
                "score": score_text,
                "score_known": score_text is not None,
                "walkover": bool(row["walkover"]),
            }
        )

    decided_matches = player_a_wins + player_b_wins
    games_total = player_a_games + player_b_games
    last_match = match_history[-1] if match_history else None

    return {
        "player_a": {
            "player_id": player_a_id,
            "player": player_a["display_name"],
            "wins": player_a_wins,
            "winrate": _percentage(player_a_wins, decided_matches),
            "games_won": player_a_games,
            "game_winrate": _percentage(player_a_games, games_total),
        },
        "player_b": {
            "player_id": player_b_id,
            "player": player_b["display_name"],
            "wins": player_b_wins,
            "winrate": _percentage(player_b_wins, decided_matches),
            "games_won": player_b_games,
            "game_winrate": _percentage(player_b_games, games_total),
        },
        "matches": len(matches),
        "decided_matches": decided_matches,
        "undecided_matches": undecided_matches,
        "matches_with_known_score": matches_with_known_score,
        "last_match": last_match,
        "history": match_history,
    }
