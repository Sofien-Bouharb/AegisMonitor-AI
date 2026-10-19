"""PostgreSQL connection helpers for AegisMonitor."""

import os

import psycopg


def connect(*, host: str | None = None) -> psycopg.Connection:
    """Connect using the project's PostgreSQL environment configuration."""
    return psycopg.connect(
        host=host or os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER", "aegis"),
        password=os.getenv("POSTGRES_PASSWORD", "aegis"),
        dbname=os.getenv("POSTGRES_DB", "aegismonitor"),
        connect_timeout=5,
    )
