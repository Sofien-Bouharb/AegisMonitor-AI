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
