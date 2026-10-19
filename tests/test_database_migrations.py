import unittest
from unittest.mock import MagicMock, patch

from ml.database.migrations import apply_migrations


class MigrationRunnerTests(unittest.TestCase):
    @patch("ml.database.migrations.MIGRATIONS_DIR")
    def test_applies_migration_on_fresh_database(self, mock_dir):
        migration = MagicMock()
        migration.stem = "001_initial_schema"
        migration.read_text.return_value = "CREATE TABLE example (id INT);"
        mock_dir.glob.return_value = [migration]

        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value.fetchone.return_value = (
            False,
        )

        result = apply_migrations(conn)

        self.assertEqual(result, ["001_initial_schema"])
        conn.transaction.assert_called_once()
        migration.read_text.assert_called_once_with(encoding="utf-8")

    @patch("ml.database.migrations.MIGRATIONS_DIR")
    def test_skips_already_applied_migration(self, mock_dir):
        migration = MagicMock()
        migration.stem = "001_initial_schema"
        mock_dir.glob.return_value = [migration]

        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (True,)
        cursor.fetchall.return_value = [("001_initial_schema",)]

        result = apply_migrations(conn)

        self.assertEqual(result, [])
        conn.transaction.assert_called_once()
        conn.transaction.return_value.__exit__.assert_called_once_with(
            None, None, None
        )
        migration.read_text.assert_not_called()


if __name__ == "__main__":
    unittest.main()
