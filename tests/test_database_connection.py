import unittest
from unittest.mock import patch

from ml.database.connection import connect


class DatabaseConnectionTests(unittest.TestCase):
    @patch("ml.database.connection.psycopg.connect")
    def test_uses_compose_compatible_defaults(self, mock_connect):
        with patch.dict("os.environ", {}, clear=True):
            connect()

        mock_connect.assert_called_once_with(
            host="localhost",
            port=5432,
            user="aegis",
            password="aegis",
            dbname="aegismonitor",
            connect_timeout=5,
        )

    @patch("ml.database.connection.psycopg.connect")
    def test_uses_environment_and_host_override(self, mock_connect):
        env = {
            "POSTGRES_HOST": "postgres",
            "POSTGRES_PORT": "5433",
            "POSTGRES_USER": "test_user",
            "POSTGRES_PASSWORD": "test_password",
            "POSTGRES_DB": "test_db",
        }
        with patch.dict("os.environ", env, clear=True):
            connect(host="db-test")

        mock_connect.assert_called_once_with(
            host="db-test",
            port=5433,
            user="test_user",
            password="test_password",
            dbname="test_db",
            connect_timeout=5,
        )


if __name__ == "__main__":
    unittest.main()
