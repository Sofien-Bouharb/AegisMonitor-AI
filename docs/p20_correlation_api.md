# AegisMonitor AI — P20 Technical Handoff Report

Report date: 2026-10-21
Project: AegisMonitor AI
Repository: ~/Projects/AegisMonitor-AI
Branch: main
Latest previously confirmed commit: 7219775 — added window corrolation to redis
Project type: Personal portfolio project, not an internship
Runtime environment: Fedora Linux, Docker Compose, local/self-hosted infrastructure

---

## 1. Objective

P20 introduces a FastAPI layer for the existing AegisMonitor AI correlation engine.

The goal is to expose signal correlation through an HTTP API and connect the P17 correlation engine to P19 Redis-backed correlation-window storage.

The implementation provides a minimal working API for:
- Receiving structured signals.
- Validating incoming requests.
- Storing and retrieving recent signals through Redis.
- Correlating recent signals per host.
- Returning incidents and their signal relationships as JSON.
- Reporting API process health.

P20 is focused on the correlation API vertical slice. It does not establish that the entire incident lifecycle or every planned integration is complete.

## 2. Architecture and responsibilities

### FastAPI

FastAPI exposes the correlation endpoints and validates incoming requests using Pydantic models.

The API is responsible for:
- Request validation.
- Converting validated request data into the existing Signal model.
- Coordinating Redis-backed signal-window storage.
- Running correlation independently for each host.
- Serializing incident results into JSON-compatible responses.
- Returning an HTTP 503 when Redis operations fail.

### P17 correlation engine

The API reuses the existing implementation in:

ml/correlation/engine.py

The correlation engine remains responsible for deciding whether recent signals form an incident and assigning relationship roles and relevance scores.

The API does not replace the engine's correlation rules.

An Isolation Forest anomaly candidate by itself must not be treated as a confirmed incident. The existing requirement for qualifying signal types remains in effect.

### Redis

Redis provides temporary correlation state through:

ml/state/correlation_window.py

The API uses the existing Redis client in:

ml/state/redis_client.py

Recent signals are grouped by host and retained inside the configured correlation window. The API retrieves the recent window after each signal is stored and correlates the resulting signals.

Redis remains an ephemeral state store, not the durable source of truth.

### PostgreSQL

PostgreSQL remains the project's durable persistence layer.

P20 does not automatically persist every incident returned by the correlation endpoint to PostgreSQL. The endpoint currently performs correlation and returns the resulting incidents; durable incident persistence is outside this API slice.

Do not describe P20 as a complete end-to-end persistence workflow.

## 3. API implementation

### Implementation files

P20 adds the following files:

- ml/api/app.py
- ml/api/Dockerfile
- tests/test_api.py

It also modifies:

- docker-compose.yml
- requirements.txt

### Health endpoint

GET /health

Returns:

{"status": "ok"}

This is a process-level health endpoint. It does not check whether Redis is reachable and should not be interpreted as a complete dependency-readiness check.

### Correlation endpoint

POST /api/v1/correlate

The request contains a list of signals.

Each signal supports:
- signal_type
- name
- occurred_at
- severity
- host
- source
- message
- metadata
- signal_id

The host defaults to localhost, and signal_id may be omitted so the existing Signal model can generate an identifier.

Validation includes:
- Unknown signal types are rejected.
- Unexpected request fields are rejected.
- Timestamps must include a timezone.
- Signal names and hosts cannot be blank.
- A request can contain at most 1,000 signals.

An empty signal list returns an empty incident result without connecting to Redis.

### Correlation workflow

For a non-empty request, the API:

1. Converts validated request entries into Signal objects.
2. Creates a Redis client.
3. Reads the configured correlation-window duration.
4. Stores each signal in its host-specific Redis window.
5. Collects the recent signal snapshot returned for each host.
6. Deduplicates the collected in-memory snapshot by the combination of host and signal ID.
7. Groups recent signals by host.
8. Runs CorrelationEngine with the matching host for each group.
9. Serializes the resulting incidents and relationships.
10. Closes the Redis client.

Redis errors produce HTTP 503 with the response detail:

Correlation state is temporarily unavailable.

The API does not silently treat a Redis failure as a successful correlation result.

### Response

The endpoint returns:
- incident_count
- incidents

Each serialized incident includes its identifier, title, host, severity, status, creation and update timestamps, rationale, and relationships.

Each relationship includes the signal identifier, type, name, role, relevance score, and first/last seen timestamps.

## 4. Docker Compose integration

The new correlation-api service is configured in docker-compose.yml.

Configuration:
- Build context: project root.
- Dockerfile: ml/api/Dockerfile.
- Container name: correlation-api.
- Compose profiles: ai and full.
- Host port: 8000.
- Redis service hostname: redis.
- Redis port: 6379.
- Redis database: 0.
- Correlation window: 300 seconds.

The Redis service is now enabled in the dev, ai, and full profiles so the API can use it in the AI and full configurations.

The API Dockerfile uses python:3.13-slim, installs dependencies from requirements.txt, copies ml/ into the image, and launches Uvicorn on 0.0.0.0:8000.

Dependencies added to requirements.txt:
- fastapi
- uvicorn
- httpx

The configured dependency ranges are:
- fastapi >=0.115,<1
- uvicorn >=0.30,<1
- httpx >=0.27,<1

Compose depends_on establishes service startup order but does not guarantee Redis is ready to accept requests. Redis failures are handled by the API with HTTP 503 responses.

## 5. P20 tests and validation

The API tests are in:

tests/test_api.py

They cover:
- Health endpoint behavior.
- Correlation of an alert and an anomaly candidate.
- Correlation across separate requests.
- Correlation for a non-default host.
- An anomaly candidate alone not creating an incident.
- Empty requests avoiding Redis access.
- Redis failure returning HTTP 503.
- Rejection of unknown signal types.
- Rejection of timestamps without timezones.
- Rejection of unexpected fields.
- Propagation of unexpected correlation-engine exceptions.

The non-default-host regression test protects against the bug where the engine's default localhost filter excluded signals from other hosts. The API now runs correlation with the host associated with each group of recent signals.

### Confirmed validation results

The following checks completed successfully on 2026-10-21:

- Full Python test suite: 58 tests passed.
- Focused API test suite: 11 tests passed.
- Live HTTP integration test against the running API and Redis passed.
- API container built and started successfully.
- GET /health returned {"status": "ok"}.
- Docker Compose configuration validated for dev, ai, and full profiles.
- git diff --check passed.

### Live Redis integration test

A fresh test host was used for two separate HTTP requests.

Request 1 submitted an anomaly candidate and returned:

{"incident_count": 0, "incidents": []}

Request 2 submitted an alert for the same host and returned one incident containing both signals.

The returned incident identified the custom host and included two relationships:
- Alert: primary.
- Anomaly: supporting.

This verifies the essential cross-request behavior against the running API and Redis rather than relying only on mocked tests.

### Warning observed

The test suite emitted a Starlette deprecation warning indicating that using httpx with starlette.testclient is deprecated and suggesting httpx2.

The warning did not cause test failures. Dependency cleanup was not included in P20 and should be handled separately if needed.

## 6. P20 scope boundaries and limitations

P20 provides a working correlation API, but it should not be described as a complete production incident-management system.

Known boundaries:

1. Incidents returned by the API are not automatically persisted to PostgreSQL by this endpoint.
2. GET /health checks the API process, not Redis readiness.
3. The API has no authentication or authorization layer in this milestone.
4. The API does not replace the existing correlation engine or modify the saved Isolation Forest model or threshold.
5. The endpoint's returned incidents are correlation results; they are not automatically proof of a confirmed real-world incident.
6. Redis startup ordering does not guarantee Redis readiness.
7. The Starlette/httpx test-client deprecation warning remains unresolved.

Do not expand the milestone into unrelated features without a concrete requirement.

## 7. P20 Git and working-tree status

At the end of P20 validation, the following working-tree changes were observed:

Modified:
- docker-compose.yml
- requirements.txt

Untracked:
- ml/api/
- tests/test_api.py

The P20 report itself is being added as:

- docs/p20_correlation_api.txt

The latest previously confirmed commit was 7219775. No P20 commit or push has been made as part of this work.

The current repository should be checked before any future commit, push, or report update. Do not assume that the working tree is clean.

## 8. Milestone closure

P20 is considered complete for its defined scope.

Implemented:
- FastAPI health endpoint.
- Validated correlation request model.
- Redis-backed correlation-window integration.
- Per-host correlation.
- JSON incident serialization.
- Redis error handling.
- Docker Compose service integration.
- API regression tests.
- Live Redis-backed cross-request integration verification.

The milestone is closed based on the passing test suite, successful runtime integration test, successful Compose validation, and clean diff check.

No commit or push has been performed.

## 9. Instructions for future work

When this report is used as project context:

- Treat P20's correlation API slice as implemented and validated.
- Preserve the P17 correlation engine's existing behavior.
- Keep PostgreSQL as the durable source of truth.
- Keep Redis as temporary operational state.
- Do not claim that the API endpoint persists incidents to PostgreSQL.
- Do not treat an anomaly candidate alone as a confirmed incident.
- Do not claim authentication, authorization, or full production readiness.
- Inspect the actual repository before proposing further changes.
- Continue one small task at a time.
- Do not commit or push without explicit user permission.

End of report.
