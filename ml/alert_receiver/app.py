
import json
import logging
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ml.database.connection import connect
from ml.database.repository import save_alert
from ml.state.deduplication import (
    claim_alert_delivery,
    deduplication_ttl_seconds,
    release_alert_delivery,
)
from ml.state.redis_client import create_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HOST = os.getenv("ALERT_RECEIVER_HOST", "0.0.0.0")
PORT = int(os.getenv("ALERT_RECEIVER_PORT", "8080"))
MAX_BODY_SIZE = 1_048_576


def parse_timestamp(value: str) -> datetime:
    """Parse an RFC 3339 timestamp into an aware datetime."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must include a timezone.")
    return parsed.astimezone(timezone.utc)


def persist_alert(alert: dict) -> bool:
    """Deduplicate and persist one Alertmanager alert.

    Returns False when an identical delivery was already processed.
    """
    labels = alert.get("labels")
    annotations = alert.get("annotations")
    fingerprint = alert.get("fingerprint")
    status = alert.get("status")

    if not isinstance(labels, dict) or not isinstance(annotations, dict):
        raise ValueError("Alert labels and annotations must be objects.")
    if not isinstance(fingerprint, str) or not fingerprint:
        raise ValueError("Alert fingerprint is required.")
    if status not in {"firing", "resolved"}:
        raise ValueError(f"Unsupported alert status: {status}")

    rule_name = labels.get("alertname")
    severity = labels.get("severity", "info")
    if not isinstance(rule_name, str) or not rule_name:
        raise ValueError("Alert label 'alertname' is required.")
    if not isinstance(severity, str):
        raise ValueError("Alert severity must be a string.")

    starts_at = alert.get("startsAt")
    if not isinstance(starts_at, str) or not starts_at:
        raise ValueError("Alert startsAt timestamp is required.")

    resolved_at = None
    if status == "resolved":
        ends_at = alert.get("endsAt")
        if not isinstance(ends_at, str) or not ends_at:
            raise ValueError("Resolved alert requires endsAt.")
        resolved_at = parse_timestamp(ends_at)

    instance = labels.get("instance")
    host = labels.get("host") or instance
    service = labels.get("service")
    environment = labels.get("environment") or labels.get("env")

    client = create_client()
    conn = None
    claimed = False
    try:
        claimed = claim_alert_delivery(
            client,
            alert,
            ttl_seconds=deduplication_ttl_seconds(),
        )
        if not claimed:
            logger.info("Skipping duplicate alert delivery: %s", fingerprint)
            return False

        conn = connect()
        save_alert(
            conn,
            fingerprint=fingerprint,
            rule_name=rule_name,
            source="alertmanager",
            severity=severity,
            status=status,
            fired_at=parse_timestamp(starts_at),
            resolved_at=resolved_at,
            labels=labels,
            annotations=annotations,
            host=host,
            service=service,
            environment=environment,
        )
        return True
    except Exception:
        if claimed:
            release_alert_delivery(client, alert)
        raise
    finally:
        if conn is not None:
            conn.close()
        client.close()


class AlertmanagerWebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/api/v1/alerts":
            self.send_error(404)
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > MAX_BODY_SIZE:
                self.send_error(413, "Invalid request body size")
                return

            payload = json.loads(self.rfile.read(content_length))
            alerts = payload.get("alerts") if isinstance(payload, dict) else None
            if not isinstance(alerts, list):
                raise ValueError("Request must contain an alerts array.")

            failures = 0
            for alert in alerts:
                try:
                    if not isinstance(alert, dict):
                        raise ValueError("Each alert must be an object.")
                    persist_alert(alert)
                except (ValueError, TypeError, KeyError) as exc:
                    failures += 1
                    logger.warning("Rejected invalid alert: %s", exc)
                except Exception:
                    failures += 1
                    logger.exception("Failed to persist alert")

            if failures:
                self.send_error(
                    500,
                    f"Failed to persist {failures} of {len(alerts)} alerts",
                )
                return

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps({"received": len(alerts)}).encode("utf-8")
            )
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            self.send_error(400, str(exc))

    def log_message(self, format_string, *args):
        logger.info("%s - %s", self.client_address[0], format_string % args)


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), AlertmanagerWebhookHandler)
    logger.info("Alertmanager webhook listening on %s:%s", HOST, PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()