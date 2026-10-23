"""PostgreSQL persistence for correlated incidents."""

import psycopg

from ml.correlation.engine import Incident, SignalType


_RELATIONSHIP_TABLES = {
    SignalType.ALERT: ("incident_alerts", "alert_id"),
    SignalType.ANOMALY: ("incident_anomalies", "anomaly_id"),
}


def save_incident(conn: psycopg.Connection, incident: Incident) -> None:
    """Persist an incident and link its existing alert/anomaly evidence atomically."""
    for relationship in incident.relationships:
        if relationship.signal_type not in _RELATIONSHIP_TABLES:
            raise NotImplementedError(
                f"Persistence for {relationship.signal_type.value} "
                "relationships is not implemented yet."
            )

    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO incidents (
                    id, title, description, status, severity,
                    host, opened_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    incident.incident_id,
                    incident.title,
                    incident.rationale,
                    incident.status,
                    incident.severity.value,
                    incident.host,
                    incident.created_at,
                    incident.updated_at,
                ),
            )

            for relationship in incident.relationships:
                table, evidence_column = _RELATIONSHIP_TABLES[
                    relationship.signal_type
                ]
                cur.execute(
                    f"""
                    INSERT INTO {table} (
                        incident_id, {evidence_column}, role, relevance,
                        first_seen_at, last_seen_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        incident.incident_id,
                        relationship.signal_id,
                        relationship.role.value,
                        relationship.relevance,
                        relationship.first_seen_at,
                        relationship.last_seen_at,
                    ),
                )

def save_alert(
    conn: psycopg.Connection,
    *,
    fingerprint: str,
    rule_name: str,
    source: str,
    severity: str,
    status: str,
    fired_at,
    labels: dict,
    annotations: dict,
    resolved_at=None,
    host: str | None = None,
    service: str | None = None,
    environment: str | None = None,
) -> None:
    """Insert or update an Alertmanager alert by its stable fingerprint."""
    from psycopg.types.json import Jsonb

    if status not in {"firing", "resolved"}:
        raise ValueError(f"Unsupported alert status: {status}")
    if severity not in {"info", "warning", "error", "critical"}:
        raise ValueError(f"Unsupported alert severity: {severity}")
    if status == "firing":
        resolved_at = None
    elif resolved_at is None:
        raise ValueError("A resolved alert requires resolved_at.")

    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO alerts (
                    fingerprint, rule_name, source, host, service,
                    environment, severity, status, fired_at, resolved_at,
                    labels, annotations
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (fingerprint) DO UPDATE SET
                    rule_name = EXCLUDED.rule_name,
                    source = EXCLUDED.source,
                    host = EXCLUDED.host,
                    service = EXCLUDED.service,
                    environment = EXCLUDED.environment,
                    severity = EXCLUDED.severity,
                    status = EXCLUDED.status,
                    fired_at = EXCLUDED.fired_at,
                    resolved_at = EXCLUDED.resolved_at,
                    labels = EXCLUDED.labels,
                    annotations = EXCLUDED.annotations,
                    updated_at = now()
                """,
                (
                    fingerprint,
                    rule_name,
                    source,
                    host,
                    service,
                    environment,
                    severity,
                    status,
                    fired_at,
                    resolved_at,
                    Jsonb(labels),
                    Jsonb(annotations),
                ),
            )

def list_recent_incidents(
    conn: psycopg.Connection,
    *,
    limit: int = 20,
) -> list[dict]:
    """Return a bounded list of recent incidents, newest first."""
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                id, title, description, status, severity, host,
                service, environment, opened_at, updated_at, resolved_at
            FROM incidents
            ORDER BY opened_at DESC, id DESC
            LIMIT %s
            """,
            (limit,),
        )
        columns = [column.name for column in cur.description]
        return [
            dict(zip(columns, row))
            for row in cur.fetchall()
        ]


def save_ai_analysis(
    conn: psycopg.Connection,
    *,
    analysis: str,
    context: dict,
) -> str:
    """Persist generated AI analysis and its evidence context; return its UUID."""
    from psycopg.types.json import Jsonb

    if not isinstance(analysis, str) or not analysis.strip():
        raise ValueError("analysis cannot be blank")
    if not isinstance(context, dict):
        raise ValueError("context must be a dictionary")

    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ai_analyses (analysis, context)
                VALUES (%s, %s)
                RETURNING id
                """,
                (analysis, Jsonb(context)),
            )
            analysis_id = cur.fetchone()[0]

    return str(analysis_id)


def save_ai_feedback(
    conn: psycopg.Connection,
    *,
    analysis_id: str,
    verdict: str,
    comment: str | None = None,
) -> str:
    """Persist human feedback for an existing AI analysis; return its UUID."""
    from uuid import UUID

    if verdict not in {"helpful", "not_helpful", "correct", "incorrect"}:
        raise ValueError("Unsupported feedback verdict")
    try:
        validated_analysis_id = UUID(analysis_id)
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("analysis_id must be a valid UUID") from exc
    if comment is not None and not isinstance(comment, str):
        raise ValueError("comment must be a string or None")

    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ai_feedback (analysis_id, verdict, comment)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (validated_analysis_id, verdict, comment),
            )
            feedback_id = cur.fetchone()[0]

    return str(feedback_id)
