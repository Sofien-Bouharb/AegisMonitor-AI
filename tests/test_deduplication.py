import unittest
from unittest.mock import Mock

from ml.state.deduplication import claim_alert_delivery


class DeduplicationTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.alert = {
            "fingerprint": "abc123",
            "status": "firing",
            "startsAt": "2026-10-20T18:00:00Z",
            "endsAt": "0001-01-01T00:00:00Z",
        }

    def test_new_delivery_is_claimed(self):
        self.client.set.return_value = True

        self.assertTrue(claim_alert_delivery(self.client, self.alert))
        self.client.set.assert_called_once()
        self.assertEqual(self.client.set.call_args.kwargs["nx"], True)
        self.assertEqual(self.client.set.call_args.kwargs["ex"], 300)

    def test_duplicate_delivery_is_rejected(self):
        self.client.set.return_value = None

        self.assertFalse(claim_alert_delivery(self.client, self.alert))

    def test_resolved_status_has_distinct_identity(self):
        self.client.set.return_value = True
        claim_alert_delivery(self.client, self.alert)
        firing_key = self.client.set.call_args.args[0]

        resolved = {**self.alert, "status": "resolved"}
        claim_alert_delivery(self.client, resolved)
        resolved_key = self.client.set.call_args.args[0]

        self.assertNotEqual(firing_key, resolved_key)

    def test_nonpositive_ttl_is_rejected(self):
        with self.assertRaises(ValueError):
            claim_alert_delivery(self.client, self.alert, ttl_seconds=0)

        self.client.set.assert_not_called()


if __name__ == "__main__":
    unittest.main()
