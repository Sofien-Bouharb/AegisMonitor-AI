-- P18: Initial durable data model for AegisMonitor.
-- This file defines the schema; applying it is a separate step.

CREATE TABLE schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE log_signatures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signature TEXT NOT NULL,
    source TEXT NOT NULL,
    description TEXT,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    occurrence_count BIGINT NOT NULL DEFAULT 1
        CHECK (occurrence_count >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_log_signatures_source_signature
        UNIQUE (source, signature),
    CONSTRAINT ck_log_signatures_seen_order
        CHECK (first_seen_at <= last_seen_at)
);

CREATE TABLE events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    occurred_at TIMESTAMPTZ NOT NULL,
    source TEXT NOT NULL,
    event_type TEXT NOT NULL,
    host TEXT NOT NULL,
    service TEXT,
    environment TEXT,
    message TEXT,
    log_signature_id UUID REFERENCES log_signatures(id) ON DELETE RESTRICT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fingerprint TEXT NOT NULL UNIQUE,
    rule_name TEXT NOT NULL,
    source TEXT NOT NULL,
    host TEXT,
    service TEXT,
    environment TEXT,
    severity TEXT NOT NULL
        CHECK (severity IN ('info', 'warning', 'error', 'critical')),
    status TEXT NOT NULL
        CHECK (status IN ('firing', 'resolved')),
    fired_at TIMESTAMPTZ NOT NULL,
    resolved_at TIMESTAMPTZ,
    labels JSONB NOT NULL DEFAULT '{}'::jsonb,
    annotations JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_alerts_resolution_order
        CHECK (resolved_at IS NULL OR resolved_at >= fired_at)
);

CREATE TABLE anomalies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name TEXT NOT NULL,
    model_version TEXT,
    host TEXT NOT NULL,
    service TEXT,
    environment TEXT,
    detected_at TIMESTAMPTZ NOT NULL,
    score DOUBLE PRECISION NOT NULL,
    severity TEXT
        CHECK (severity IS NULL OR
               severity IN ('info', 'warning', 'error', 'critical')),
    status TEXT NOT NULL DEFAULT 'candidate',
    features JSONB NOT NULL DEFAULT '{}'::jsonb,
    explanation TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'acknowledged', 'resolved', 'closed')),
    severity TEXT NOT NULL
        CHECK (severity IN ('info', 'warning', 'error', 'critical')),
    host TEXT,
    service TEXT,
    environment TEXT,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_incidents_resolution_order
        CHECK (resolved_at IS NULL OR resolved_at >= opened_at)
);

-- Typed junctions preserve real foreign-key integrity.
-- Removing an incident removes its junction rows, not the evidence.

CREATE TABLE incident_alerts (
    incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    alert_id UUID NOT NULL REFERENCES alerts(id) ON DELETE RESTRICT,
    role TEXT NOT NULL
        CHECK (role IN ('primary', 'contributing', 'supporting', 'evidence')),
    relevance DOUBLE PRECISION NOT NULL CHECK (relevance BETWEEN 0 AND 1),
    first_seen_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (incident_id, alert_id),
    CHECK (first_seen_at <= last_seen_at)
);

CREATE TABLE incident_anomalies (
    incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    anomaly_id UUID NOT NULL REFERENCES anomalies(id) ON DELETE RESTRICT,
    role TEXT NOT NULL
        CHECK (role IN ('primary', 'contributing', 'supporting', 'evidence')),
    relevance DOUBLE PRECISION NOT NULL CHECK (relevance BETWEEN 0 AND 1),
    first_seen_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (incident_id, anomaly_id),
    CHECK (first_seen_at <= last_seen_at)
);

CREATE TABLE incident_events (
    incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
    role TEXT NOT NULL
        CHECK (role IN ('primary', 'contributing', 'supporting', 'evidence')),
    relevance DOUBLE PRECISION NOT NULL CHECK (relevance BETWEEN 0 AND 1),
    first_seen_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (incident_id, event_id),
    CHECK (first_seen_at <= last_seen_at)
);

CREATE TABLE incident_log_signatures (
    incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    log_signature_id UUID NOT NULL
        REFERENCES log_signatures(id) ON DELETE RESTRICT,
    role TEXT NOT NULL
        CHECK (role IN ('primary', 'contributing', 'supporting', 'evidence')),
    relevance DOUBLE PRECISION NOT NULL CHECK (relevance BETWEEN 0 AND 1),
    first_seen_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (incident_id, log_signature_id),
    CHECK (first_seen_at <= last_seen_at)
);

-- The primary keys index incident -> evidence lookups.
-- These indexes support evidence -> incident lookups.

CREATE INDEX idx_events_occurred_at ON events (occurred_at DESC);
CREATE INDEX idx_events_host_occurred_at ON events (host, occurred_at DESC);
CREATE INDEX idx_alerts_status_fired_at ON alerts (status, fired_at DESC);
CREATE INDEX idx_anomalies_host_detected_at
    ON anomalies (host, detected_at DESC);
CREATE INDEX idx_incidents_status_updated_at
    ON incidents (status, updated_at DESC);

CREATE INDEX idx_incident_alerts_alert_id ON incident_alerts (alert_id);
CREATE INDEX idx_incident_anomalies_anomaly_id
    ON incident_anomalies (anomaly_id);
CREATE INDEX idx_incident_events_event_id ON incident_events (event_id);
CREATE INDEX idx_incident_log_signatures_signature_id
    ON incident_log_signatures (log_signature_id);

INSERT INTO schema_migrations (version)
VALUES ('001_initial_schema');
