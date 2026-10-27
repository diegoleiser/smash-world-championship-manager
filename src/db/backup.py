"""Consistent copies of the SQLite database before larger writes."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path


def backup_database(
    db_path: str | Path,
    label: str,
    *,
    now: datetime | None = None,
) -> Path:
    """Copy the database next to itself as ``<name>_before_<label>_<time>.db``.

    The SQLite backup API gives a consistent copy even while other
    connections are open.
    """

    db_path = Path(db_path)
    timestamp = (now or datetime.now()).strftime("%Y-%m-%d_%H-%M-%S")
    target = db_path.with_name(
        f"{db_path.stem}_before_{label}_{timestamp}{db_path.suffix}"
    )
    if target.exists():
        raise FileExistsError(f"Backup already exists: {target}")
    with closing(sqlite3.connect(db_path)) as source:
        with closing(sqlite3.connect(target)) as copy:
            source.backup(copy)
    return target
