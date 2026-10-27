"""Bring an existing database up to the current schema."""

from __future__ import annotations

import argparse
import sqlite3
from contextlib import closing
from pathlib import Path

from db.migrations import (
    MigrationError,
    available_migrations,
    database_version,
    migrate_database,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "data" / "smash_wm.db"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Apply pending schema migrations to an existing database. "
            "A backup is written next to the database first."
        )
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show the current level and pending migrations without writing",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        if not args.db.exists():
            raise FileNotFoundError(f"Database not found: {args.db}")
        if args.dry_run:
            version = database_version(args.db)
            uri = f"{args.db.resolve().as_uri()}?mode=ro"
            with closing(sqlite3.connect(uri, uri=True)) as connection:
                recorded = connection.execute(
                    "PRAGMA user_version"
                ).fetchone()[0]
            pending = [
                migration.name
                for migration in available_migrations()
                if migration.version > version
            ]
            note = "" if recorded == version else " (recognised, not yet recorded)"
            print(f"Database level: {version}{note}")
            print(f"Pending migrations: {', '.join(pending) or 'none'}")
            return
        result = migrate_database(args.db)
    except (
        FileNotFoundError,
        FileExistsError,
        MigrationError,
        sqlite3.Error,
    ) as error:
        raise SystemExit(f"Migration failed: {error}") from error

    if result.backup_path is None:
        print(f"Database is up to date (level {result.to_version}).")
        return
    print(f"Backup: {result.backup_path}")
    if result.applied:
        print(f"Applied: {', '.join(result.applied)}")
    print(f"Database level: {result.from_version} -> {result.to_version}")


if __name__ == "__main__":
    main()
