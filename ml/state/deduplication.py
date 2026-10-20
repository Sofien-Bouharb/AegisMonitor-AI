"""Temporary Redis-backed deduplication for alert deliveries."""

import hashlib
import json
import os

import redis


DEFAULT_TTL_SECONDS = 300
KEY_PREFIX = "aegis:dedup:alert:"


def alert_delivery_key(alert: dict) -> str:
    """Build a stable key for one alert status/timestamp combination."""
    identity = {
        "fingerprint": alert.get("fingerprint"),
        "status": alert.get("status"),
        "startsAt": alert.get("startsAt"),
        "endsAt": alert.get("endsAt"),
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return f"{KEY_PREFIX}{digest}"


def claim_alert_delivery(
    client: redis.Redis,
    alert: dict,
    *,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> bool:
    """Return True for a new delivery, False for a duplicate."""
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be positive")

    return bool(
        client.set(
            alert_delivery_key(alert),
            "1",
            nx=True,
            ex=ttl_seconds,
        )
    )


def release_alert_delivery(client: redis.Redis, alert: dict) -> None:
    """Remove a claim when durable persistence fails."""
    client.delete(alert_delivery_key(alert))


def deduplication_ttl_seconds() -> int:
    """Read the delivery deduplication TTL from the environment."""
    value = int(os.getenv("REDIS_DEDUP_TTL_SECONDS", str(DEFAULT_TTL_SECONDS)))
    if value <= 0:
        raise ValueError("REDIS_DEDUP_TTL_SECONDS must be positive")
    return value
