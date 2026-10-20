"""Redis client configuration for AegisMonitor ephemeral state."""

import os

import redis


def create_client() -> redis.Redis:
    """Create a Redis client using environment configuration."""
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=int(os.getenv("REDIS_DB", "0")),
        password=os.getenv("REDIS_PASSWORD") or None,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )


def check_connection(client: redis.Redis) -> bool:
    """Return whether Redis responds to a PING."""
    return bool(client.ping())
