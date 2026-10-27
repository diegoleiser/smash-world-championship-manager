"""Shared database access and player resolution for statistics services."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from db.connection import open_sqlite_connection


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "smash_wm.db"

# Every participation the archive knows: all participant rows, plus the
# champion of a tournament whose participants were never recorded (for some
# early tournaments only the winner is known). The champion counts as an
# appearance with placement 1; nobody else is assumed. Use it as a subquery,
# e.g. ``FROM (`` + KNOWN_PARTICIPANTS_SQL + ``) AS tp``. Columns:
# tournament_id, player_id, placement, seed and ``recorded`` (1 for a
# participant row, 0 for a champion known only from the tournament).
KNOWN_PARTICIPANTS_SQL = """
    SELECT tournament_id, player_id, placement, seed, 1 AS recorded
    FROM tournament_participants
    UNION ALL
    SELECT t.tournament_id, t.winner_id, 1, NULL, 0
    FROM tournaments AS t
    WHERE t.winner_id IS NOT NULL
      AND NOT EXISTS (
          SELECT 1
          FROM tournament_participants AS recorded
          WHERE recorded.tournament_id = t.tournament_id
            AND recorded.player_id = t.winner_id
      )
"""


class PlayerNotFoundError(ValueError):
    """Raised when a player cannot be found."""


def connect_db(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open the SQLite database with named columns."""

    return open_sqlite_connection(db_path)


def resolve_player(
    connection: sqlite3.Connection,
    player_reference: str,
) -> sqlite3.Row:
    """Find a player by ID or case-insensitive display name."""

    player = connection.execute(
        """
        SELECT
            player_id,
            display_name,
            core_player,
            active,
            notes
        FROM players
        WHERE player_id = ?
           OR lower(display_name) = lower(?)
        LIMIT 1
        """,
        (player_reference, player_reference),
    ).fetchone()

    if player is None:
        raise PlayerNotFoundError(
            f"Player not found: {player_reference}"
        )

    return player
