"""Bring an existing SQLite database up to the current schema.

The database records its migration level in ``PRAGMA user_version``. Older
databases were migrated before that existed and still report 0; their level
is recognised from the objects each migration created. Pending migrations run
one at a time, each in its own transaction, after a backup of the database.
"""

from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"
MIGRATE_COMMAND = "python src/migrate_db.py"

_MIGRATION_FILE = re.compile(r"^(\d{3})_[a-z0-9_]+\.sql$")

# Tables (column None) or columns each migration created, used to recognise
# databases migrated before the level was recorded in user_version.
LEGACY_MARKERS: dict[int, tuple[tuple[str, str | None], ...]] = {
    1: (
        ("tournament_drafts", None),
        ("tournament_draft_participants", None),
    ),
    2: (
        ("tournament_draft_groups", None),
        ("tournament_draft_group_members", None),
    ),
    3: (("tournament_draft_group_matches", None),),
    4: (
        ("tournament_draft_bracket_seeds", None),
        ("tournament_draft_bracket_matches", None),
        ("tournament_draft_bracket_routes", None),
    ),
    5: (
        ("matches", "stage"),
        ("matches", "suggested_play_order"),
        ("matches", "completed_at"),
    ),
}


class MigrationError(RuntimeError):
    """Raised when a database cannot be migrated safely."""


@dataclass(frozen=True)
class Migration:
    version: int
    path: Path

    @property
    def name(self) -> str:
        return self.path.stem


@dataclass(frozen=True)
class MigrationResult:
    from_version: int
    to_version: int
    applied: list[str]
    backup_path: Path | None


def available_migrations(
    migrations_dir: Path = MIGRATIONS_DIR,
) -> list[Migration]:
    """Return the numbered migrations in order; numbers must have no gaps."""

    migrations = []
    for path in sorted(migrations_dir.glob("*.sql")):
        match = _MIGRATION_FILE.match(path.name)
        if match is None:
            raise MigrationError(f"Unexpected migration file name: {path.name}")
        migrations.append(Migration(int(match.group(1)), path))
    expected = list(range(1, len(migrations) + 1))
    if [migration.version for migration in migrations] != expected:
        raise MigrationError("Migration numbers must run from 001 without gaps.")
    return migrations


def latest_version(migrations_dir: Path = MIGRATIONS_DIR) -> int:
    """Return the schema level a fully migrated database has."""

    return len(available_migrations(migrations_dir))


def _marker_state(
    connection: sqlite3.Connection,
    markers: tuple[tuple[str, str | None], ...],
) -> str:
    present = 0
    for table, column in markers:
        columns = {
            row[1]
            for row in connection.execute(
                "SELECT * FROM pragma_table_info(?)",
                (table,),
            )
        }
        if columns and (column is None or column in columns):
            present += 1
    if present == len(markers):
        return "complete"
    return "missing" if present == 0 else "partial"


def detect_version(connection: sqlite3.Connection) -> int:
    """Return the database's migration level.

    A recorded ``user_version`` wins. Otherwise the level is the longest run
    of legacy migrations, from 001 on, whose objects all exist. Objects of a
    later migration beyond that run, or only part of one migration, mean the
    database was changed by hand, and a ``MigrationError`` is raised.
    """

    recorded = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if recorded:
        return recorded

    states = [
        _marker_state(connection, LEGACY_MARKERS[version])
        for version in sorted(LEGACY_MARKERS)
    ]
    level = 0
    while level < len(states) and states[level] == "complete":
        level += 1
    unexpected = [
        f"{version:03d}"
        for version, state in enumerate(states, start=1)
        if version > level and state != "missing"
    ]
    if unexpected:
        raise MigrationError(
            "The database has objects of migration "
            f"{', '.join(unexpected)} without a complete level before them; "
            "check it by hand before migrating."
        )
    return level


def database_version(db_path: Path) -> int:
    """Read a database's migration level without writing to it."""

    uri = f"{Path(db_path).resolve().as_uri()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        return detect_version(connection)


def backup_database(
    db_path: Path,
    label: str,
    *,
    now: datetime | None = None,
) -> Path:
    """Copy the database next to itself as ``<name>_before_<label>_<time>.db``."""

    timestamp = (now or datetime.now()).strftime("%Y-%m-%d_%H-%M-%S")
    target = db_path.with_name(
        f"{db_path.stem}_before_{label}_{timestamp}{db_path.suffix}"
    )
    if target.exists():
        raise MigrationError(f"Backup already exists: {target}")
    with closing(sqlite3.connect(db_path)) as source:
        with closing(sqlite3.connect(target)) as copy:
            source.backup(copy)
    return target


def migrate_database(
    db_path: Path,
    migrations_dir: Path = MIGRATIONS_DIR,
    *,
    now: datetime | None = None,
) -> MigrationResult:
    """Apply pending migrations after a backup and record the new level.

    A database that is already current is left untouched. A legacy database
    whose level was only recognised gets that level recorded, also after a
    backup. A failing migration is rolled back; earlier ones stay applied and
    recorded, and the backup holds the state before the run.
    """

    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")
    migrations = available_migrations(migrations_dir)

    with closing(sqlite3.connect(db_path)) as connection:
        if _marker_state(connection, (("players", None),)) != "complete":
            raise MigrationError(
                "The database has no base schema; create it with init_db.py."
            )
        recorded = int(connection.execute("PRAGMA user_version").fetchone()[0])
        version = detect_version(connection)
        if version > len(migrations):
            raise MigrationError(
                f"The database is at level {version}, newer than this code "
                f"({len(migrations)})."
            )
        pending = [
            migration for migration in migrations if migration.version > version
        ]
        if not pending and recorded == version:
            return MigrationResult(version, version, [], None)

        label = (
            f"migration_{pending[0].version:03d}"
            if pending
            else f"migration_level_{version:03d}"
        )
        backup_path = backup_database(db_path, label, now=now)

        if not pending:
            connection.execute(f"PRAGMA user_version = {version}")
            return MigrationResult(version, version, [], backup_path)

        applied = []
        for migration in pending:
            script = migration.path.read_text(encoding="utf-8")
            try:
                connection.executescript(
                    "BEGIN;\n"
                    f"{script}\n"
                    f"PRAGMA user_version = {migration.version};\n"
                    "COMMIT;"
                )
            except sqlite3.Error as error:
                if connection.in_transaction:
                    connection.rollback()
                raise MigrationError(
                    f"Migration {migration.name} failed and was rolled back: "
                    f"{error}. Backup: {backup_path}"
                ) from error
            applied.append(migration.name)

    return MigrationResult(version, pending[-1].version, applied, backup_path)
