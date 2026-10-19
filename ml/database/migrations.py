"""Transactional SQL migration runner for AegisMonitor."""

from pathlib import Path

import psycopg
from psycopg import sql

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"
MIGRATION_TABLE = "schema_migrations"


def apply_migrations(conn: psycopg.Connection) -> list[str]:
    """Apply pending migrations atomically and return their version names."""
    applied_now = []

    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = current_schema()
                      AND table_name = %s
                )
                """,
                (MIGRATION_TABLE,),
            )
            history_exists = cur.fetchone()[0]

            applied = set()
            if history_exists:
                cur.execute(
                    sql.SQL("SELECT version FROM {}").format(
                        sql.Identifier(MIGRATION_TABLE)
                    )
                )
                applied = {row[0] for row in cur.fetchall()}

            for migration_path in sorted(
                MIGRATIONS_DIR.glob("[0-9]*.sql")
            ):
                version = migration_path.stem
                if version in applied:
                    continue

                cur.execute(migration_path.read_text(encoding="utf-8"))
                applied_now.append(version)
                applied.add(version)

    return applied_now
