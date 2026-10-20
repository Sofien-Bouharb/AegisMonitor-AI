import unittest
from unittest.mock import patch

from ml.state.redis_client import check_connection, create_client


class RedisClientTests(unittest.TestCase):
    @patch.dict("os.environ", {}, clear=True)
    def test_uses_local_defaults(self):
        client = create_client()

        self.assertEqual(client.connection_pool.connection_kwargs["host"], "localhost")
        self.assertEqual(client.connection_pool.connection_kwargs["port"], 6379)
        self.assertEqual(client.connection_pool.connection_kwargs["db"], 0)
        self.assertIsNone(client.connection_pool.connection_kwargs["password"])
        self.assertTrue(client.connection_pool.connection_kwargs["decode_responses"])

    @patch.dict(
        "os.environ",
        {
            "REDIS_HOST": "redis",
            "REDIS_PORT": "6380",
            "REDIS_DB": "2",
            "REDIS_PASSWORD": "test-secret",
        },
    )
    def test_uses_environment_configuration(self):
        client = create_client()

        self.assertEqual(client.connection_pool.connection_kwargs["host"], "redis")
        self.assertEqual(client.connection_pool.connection_kwargs["port"], 6380)
        self.assertEqual(client.connection_pool.connection_kwargs["db"], 2)
        self.assertEqual(client.connection_pool.connection_kwargs["password"], "test-secret")


    def test_health_check_returns_true_when_ping_succeeds(self):
        from unittest.mock import Mock

        client = Mock()
        client.ping.return_value = True
        self.assertTrue(check_connection(client))
        client.ping.assert_called_once_with()

    def test_health_check_returns_false_when_ping_is_false(self):
        from unittest.mock import Mock

        client = Mock()
        client.ping.return_value = False
        self.assertFalse(check_connection(client))
        client.ping.assert_called_once_with()


    def test_health_check_returns_true_when_ping_succeeds(self):
        from unittest.mock import Mock

        client = Mock()
        client.ping.return_value = True
        self.assertTrue(check_connection(client))
        client.ping.assert_called_once_with()

    def test_health_check_returns_false_when_ping_is_false(self):
        from unittest.mock import Mock

        client = Mock()
        client.ping.return_value = False
        self.assertFalse(check_connection(client))
        client.ping.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
