import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from ml.correlation.engine import Severity, Signal, SignalType
from ml.state.correlation_window import (
    correlation_window_seconds,
    deserialize_signal,
    host_payload_key,
    host_signal_key,
    serialize_signal,
    store_signal,
)


class CorrelationWindowTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 20, 18, 0, tzinfo=timezone.utc)
        self.client = Mock()
        self.client.zrangebyscore.return_value = []
        self.client.hmget.return_value = []

    def make_signal(
        self,
        signal_type=SignalType.ALERT,
        minutes_ago=0,
        host="localhost",
        signal_id=None,
        message="test signal",
    ):
        return Signal(
            signal_type=signal_type,
            name=f"test-{signal_type.value}",
            occurred_at=self.now - timedelta(minutes=minutes_ago),
            severity=Severity.WARNING,
            host=host,
            source="unit-test",
            message=message,
            metadata={"test": True},
            signal_id=signal_id or f"signal-{signal_type.value}-{minutes_ago}-{host}",
        )

    def test_serialization_round_trip(self):
        signal = self.make_signal(SignalType.ANOMALY)
        self.assertEqual(deserialize_signal(serialize_signal(signal)), signal)

    def test_host_keys_are_host_specific(self):
        self.assertEqual(
            host_signal_key("server-a"),
            "aegis:correlation:host:server-a",
        )
        self.assertEqual(
            host_payload_key("server-a"),
            "aegis:correlation:host:server-a:payloads",
        )
        self.assertNotEqual(host_signal_key("server-a"), host_signal_key("server-b"))

    def test_rejects_empty_host(self):
        with self.assertRaises(ValueError):
            host_signal_key(" ")

    @patch.dict("os.environ", {}, clear=True)
    def test_default_window_is_five_minutes(self):
        self.assertEqual(correlation_window_seconds(), 300)

    @patch.dict("os.environ", {"REDIS_CORRELATION_WINDOW_SECONDS": "120"})
    def test_window_can_be_configured(self):
        self.assertEqual(correlation_window_seconds(), 120)

    @patch.dict("os.environ", {"REDIS_CORRELATION_WINDOW_SECONDS": "0"})
    def test_rejects_non_positive_configured_window(self):
        with self.assertRaises(ValueError):
            correlation_window_seconds()

    def test_store_uses_signal_id_as_sorted_set_member(self):
        signal = self.make_signal()
        self.client.zrangebyscore.return_value = [signal.signal_id]
        self.client.hmget.return_value = [serialize_signal(signal)]

        result = store_signal(
            self.client, signal, window_seconds=300, now=self.now
        )

        key = host_signal_key(signal.host)
        payload_key = host_payload_key(signal.host)
        cutoff = (self.now - timedelta(seconds=300)).timestamp()

        self.client.zadd.assert_called_once_with(
            key, {signal.signal_id: signal.occurred_at.timestamp()}
        )
        self.client.hset.assert_called_once_with(
            payload_key, signal.signal_id, serialize_signal(signal)
        )
        self.client.zrangebyscore.assert_any_call(key, "-inf", cutoff)
        self.client.zrangebyscore.assert_any_call(key, cutoff, "+inf")
        self.client.hmget.assert_called_once_with(payload_key, [signal.signal_id])
        self.assertEqual(result, [signal])

    def test_expired_signals_are_removed_from_index_and_payloads(self):
        signal = self.make_signal(minutes_ago=10)
        self.client.zrangebyscore.side_effect = [
            [signal.signal_id],
            [],
        ]

        result = store_signal(
            self.client, signal, window_seconds=300, now=self.now
        )

        key = host_signal_key(signal.host)
        payload_key = host_payload_key(signal.host)
        self.client.zrem.assert_called_once_with(key, signal.signal_id)
        self.client.hdel.assert_called_once_with(payload_key, signal.signal_id)
        self.assertEqual(result, [])

    def test_same_signal_id_updates_existing_member(self):
        first = self.make_signal(signal_id="stable-id", message="original")
        updated = self.make_signal(signal_id="stable-id", message="updated")

        store_signal(self.client, first, now=self.now)
        store_signal(self.client, updated, now=self.now)

        self.assertEqual(self.client.zadd.call_count, 2)
        self.assertEqual(self.client.hset.call_count, 2)
        self.assertEqual(
            self.client.hset.call_args.args[1:],
            ("stable-id", serialize_signal(updated)),
        )

    def test_store_rejects_non_positive_window(self):
        with self.assertRaises(ValueError):
            store_signal(
                self.client,
                self.make_signal(),
                window_seconds=0,
                now=self.now,
            )

    def test_store_rejects_naive_current_time(self):
        with self.assertRaises(ValueError):
            store_signal(
                self.client,
                self.make_signal(),
                now=datetime(2026, 10, 20, 18, 0),
            )


if __name__ == "__main__":
    unittest.main()