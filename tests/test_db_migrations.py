"""Tests for migrating existing databases to the current schema."""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime
from pathlib import Path

import challonge_import
from db.migrations import (
    MigrationError,
    available_migrations,
    database_version,
    detect_version,
    latest_version,
    migrate_database,
)
from init_db import DEFAULT_MIGRATIONS_DIR, DEFAULT_SCHEMA_PATH


NOW = datetime(2026, 10, 27, 12, 0, 0)


def build_legacy_database(db_path: Path, level: int) -> None:
    """Create a database migrated by hand up to ``level``, version unrecorded."""

    with closing(sqlite3.connect(db_path)) as connection:
        connection.executescript(DEFAULT_SCHEMA_PATH.read_text(encoding="utf-8"))
        for migration in available_migrations()[:level]:
            connection.executescript(migration.path.read_text(encoding="utf-8"))


def read_version(db_path: Path) -> int:
    with closing(sqlite3.connect(db_path)) as connection:
        return connection.execute("PRAGMA user_version").fetchone()[0]


def table_exists(db_path: Path, table: str) -> bool:
    with closing(sqlite3.connect(db_path)) as connection:
        return connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone() is not None


class MigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        self.db_path = self.directory / "smash.db"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def backups(self) -> list[Path]:
        return sorted(self.directory.glob("smash_before_*.db"))

    def test_migrations_are_numbered_without_gaps(self) -> None:
        names = [migration.name for migration in available_migrations()]

        self.assertEqual(len(names), latest_version())
        self.assertTrue(names[0].startswith("001_"))

    def test_legacy_level_is_recognised_from_existing_objects(self) -> None:
        for level in range(latest_version() + 1):
            with self.subTest(level=level):
                db_path = self.directory / f"legacy_{level}.db"
                build_legacy_database(db_path, level)
                with closing(sqlite3.connect(db_path)) as connection:
                    self.assertEqual(detect_version(connection), level)

    def test_inconsistent_legacy_objects_are_refused(self) -> None:
        build_legacy_database(self.db_path, 2)
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute("ALTER TABLE matches ADD COLUMN stage TEXT")
            connection.commit()

        with self.assertRaises(MigrationError):
            database_version(self.db_path)
        with self.assertRaises(MigrationError):
            migrate_database(self.db_path, now=NOW)
        self.assertEqual(self.backups(), [])

    def test_pending_migrations_run_after_a_backup(self) -> None:
        build_legacy_database(self.db_path, 3)

        result = migrate_database(self.db_path, now=NOW)

        self.assertEqual((result.from_version, result.to_version), (3, 5))
        self.assertEqual(
            result.applied,
            [migration.name for migration in available_migrations()[3:]],
        )
        self.assertEqual(
            result.backup_path,
            self.directory / "smash_before_migration_004_2026-10-27_12-00-00.db",
        )
        self.assertEqual(read_version(self.db_path), 5)
        self.assertTrue(table_exists(self.db_path, "tournament_draft_bracket_matches"))
        # The backup keeps the state before the run.
        self.assertFalse(
            table_exists(result.backup_path, "tournament_draft_bracket_matches")
        )
        self.assertEqual(read_version(result.backup_path), 0)

    def test_current_legacy_database_only_records_its_level(self) -> None:
        build_legacy_database(self.db_path, 5)

        first = migrate_database(self.db_path, now=NOW)
        second = migrate_database(self.db_path, now=NOW)

        self.assertEqual(first.applied, [])
        self.assertIsNotNone(first.backup_path)
        self.assertEqual(read_version(self.db_path), 5)
        self.assertIsNone(second.backup_path)
        self.assertEqual(len(self.backups()), 1)

    def test_reading_the_level_does_not_write(self) -> None:
        build_legacy_database(self.db_path, 5)
        before = self.db_path.read_bytes()

        self.assertEqual(database_version(self.db_path), 5)
        self.assertEqual(self.db_path.read_bytes(), before)

    def test_failing_migration_is_rolled_back(self) -> None:
        migrations_dir = self.directory / "migrations"
        shutil.copytree(DEFAULT_MIGRATIONS_DIR, migrations_dir)
        (migrations_dir / "006_broken.sql").write_text(
            "CREATE TABLE half_done (value INTEGER);\n"
            "INSERT INTO missing_table VALUES (1);\n",
            encoding="utf-8",
        )
        build_legacy_database(self.db_path, 5)
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute("PRAGMA user_version = 5")

        with self.assertRaises(MigrationError):
            migrate_database(self.db_path, migrations_dir, now=NOW)

        self.assertEqual(read_version(self.db_path), 5)
        self.assertFalse(table_exists(self.db_path, "half_done"))
        self.assertEqual(len(self.backups()), 1)

    def test_database_without_base_schema_is_refused(self) -> None:
        sqlite3.connect(self.db_path).close()

        with self.assertRaises(MigrationError):
            migrate_database(self.db_path, now=NOW)

    def test_import_requires_the_current_schema(self) -> None:
        build_legacy_database(self.db_path, 3)

        with closing(sqlite3.connect(self.db_path)) as connection:
            with self.assertRaisesRegex(ValueError, "migrate_db.py"):
                challonge_import.require_current_schema(connection)


if __name__ == "__main__":
    unittest.main()
