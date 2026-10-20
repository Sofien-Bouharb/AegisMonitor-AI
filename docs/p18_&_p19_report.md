# AegisMonitor AI — P18 & P19 Technical Handoff Report

**Report date:** 2026-10-20  
**Project:** AegisMonitor AI  
**Repository:** `~/Projects/AegisMonitor-AI`  
**Branch:** `main`  
**Remote:** `origin/main`  
**Latest confirmed commit:** `7219775` — `added window corrolation to redis`  
**Project type:** Personal portfolio project, not an internship  
**Runtime environment:** Fedora Linux, Docker Compose, local/self-hosted infrastructure

---

## 1. Project context and engineering principles

AegisMonitor AI is a local, self-hosted infrastructure monitoring and anomaly-detection project. Its goals include demonstrating practical skills in:

- DevOps and observability
- Machine-learning anomaly detection
- MLOps and telemetry processing
- Cybersecurity and system reliability
- Backend development and data modeling
- Distributed systems and state management

The core project should not depend on a cloud service.

Important engineering constraints:

1. Prefer an MVP that works over unnecessary complexity.
2. Inspect the repository and existing implementation before proposing changes.
3. Work on one small task at a time.
4. Explain the task briefly, provide one command or action, and wait for the output.
5. Preserve existing functionality and tests.
6. Do not casually modify the Isolation Forest model, its saved threshold, or the P17 correlation engine.
7. PostgreSQL is the durable source of truth.
8. Redis is used for ephemeral state, coordination, and short-lived operational data.
9. Do not commit or push changes unless explicitly requested.
10. Do not claim that deferred or partially implemented functionality is complete.

## 2. Milestone overview

| Milestone | Purpose | State |
|---|---|---|
| P17 | Correlation engine and signal modeling | Completed |
| P18 | PostgreSQL persistence integration | Implemented persistence slice; see scope notes below |
| P19 | Redis integration | Closed with intentionally reduced scope |
| P20 | FastAPI correlation/API layer | Next milestone |

The user has intentionally decided to stop expanding P19 because of time constraints. The two implemented Redis features are considered sufficient for the current project scope.

---

# PART I — P18: PostgreSQL Integration

## 3. Objective

P18 introduced durable database persistence for the correlation and alert-processing portions of AegisMonitor AI.

Before this work, the anomaly exporter evaluated telemetry and exposed Prometheus metrics, but it did not create durable anomaly records in PostgreSQL. The P18 work established database infrastructure and repository-level persistence so that incidents and alert relationships could be stored.

The implementation must be understood as a concrete persistence slice, not proof that every persistence capability in the original roadmap has been implemented.

## 4. Architecture and responsibilities

### PostgreSQL

PostgreSQL is the durable store for supported records and relationships.

The database layer is responsible for:

- Database connectivity
- Persistence operations
- Referential integrity enforcement
- Transaction and rollback behavior
- Incident persistence
- Supported alert/anomaly relationships

### Repository layer

The repository encapsulates database operations so that higher-level code can persist records without embedding raw SQL throughout the application.

The repository includes `save_incident` and relationship-persistence functionality for supported signal types.

### Correlation engine

The P17 correlation engine remains separate from the persistence implementation. P18 supplies persistence capabilities; it should not be assumed that the complete correlation lifecycle is already exposed through an API.

### Anomaly exporter

The existing anomaly exporter evaluates telemetry periodically, approximately every 15 seconds, and exposes anomaly score and candidate metrics through Prometheus.

The exporter preserves the saved Isolation Forest threshold. It does not automatically create a durable anomaly record every time it flags a candidate.

An anomaly candidate is not equivalent to a confirmed incident.

## 5. Data-model and persistence boundaries

The project uses the conceptual distinction:

- **Event:** an observed occurrence.
- **Alert:** an actionable notification or condition.
- **Anomaly:** a model-generated candidate indicating unusual behavior.
- **Incident:** a correlated, higher-level operational occurrence.

These entities must not be collapsed into one generic signal table without a deliberate design decision.

A LogSignature is associated with log-origin events. It is not automatically applicable to every alert or anomaly.

The intended incident-to-signal relationship is many-to-many, with explicit per-type junction tables and relationship metadata such as role and relevance score. Roles discussed in the design include `primary`, `contributing`, `supporting`, and `evidence`.

**Important scope qualification:** the implemented repository supports Alert and Anomaly relationships. Persistence for log-signature relationships raises `NotImplementedError`. Do not assume complete Event or LogSignature persistence simply because the broader data model defines those concepts.

## 6. P18 implementation and files

The following areas were involved in the P18 implementation:

- `migrations/`
- `ml/database/`
- `requirements.txt`
- Database-related tests

The repository's database module provides the persistence/repository functionality, including incident persistence and supported signal relationships.

The migration directory contains the database schema setup introduced during this milestone.

The exact complete file inventory, individual migration filenames, and final table/column definitions were not preserved in this handoff. Inspect the current repository before modifying migrations or assuming the exact schema.

## 7. P18 validation

The following checks were reported as successful:

- 15 database-related tests passed.
- Live PostgreSQL connectivity was verified.
- Foreign-key enforcement was verified.
- Transaction rollback behavior was verified.
- Incident persistence was verified.
- Alert-to-incident linkage was verified.

These checks establish that the implemented persistence slice works for its supported use cases.

They do not establish that every entity and relationship in the original roadmap has full persistence support.

## 8. P18 known limitations and deferred capabilities

The original roadmap described broader persistence responsibilities, including:

- Incidents
- Alerts
- Anomalies
- Log signatures and events
- Signal-to-incident relationships
- Status and history
- AI analysis
- Feedback

The implementation must not be described as fully covering all these capabilities without further repository verification.

Known limitations include:

1. Log-signature relationship persistence is not implemented.
2. Event/LogSignature persistence is not established as complete.
3. The anomaly exporter still exposes model results as metrics; it does not automatically persist each anomaly candidate.
4. The full end-to-end API workflow for correlation, persistence, and querying belongs to subsequent integration work.

These are scope boundaries for future work, not reasons to discard the existing implementation.

## 9. P18 Git checkpoint

The P18 integration checkpoint is:

`e755b7e` — `p18: postgres integration_2`

The commit was subsequently followed by the P19 Redis work.

The latest known remote history includes this P18 checkpoint, but P18 should be reviewed from the current repository rather than reconstructed from the commit message alone.

---

# PART II — P19: Redis Integration

## 10. Objective and final scope decision

P19 introduced Redis for two immediately useful operational capabilities:

1. Alert-delivery deduplication.
2. Temporary, per-host correlation-window signal storage.

The original Redis roadmap also included cooldowns, rate limiting, temporary-state handling, and caching.

**The user explicitly decided to close P19 after the two implemented features because time is limited.** Cooldowns, rate limiting, and caching are intentionally deferred.

Do not reopen P19 simply to finish every originally proposed Redis feature. Future work should prioritize the next milestone and only revisit these features if a concrete requirement justifies it.

## 11. Redis client and configuration

### Implementation files

The Redis integration introduced or modified the following files.

New files in the first P19 slice:

- `ml/state/__init__.py`
- `ml/state/deduplication.py`
- `ml/state/redis_client.py`
- `tests/test_deduplication.py`
- `tests/test_redis_client.py`

Additional files modified in that slice:

- `docker-compose.yml`
- `ml/alert_receiver/app.py`
- `requirements.txt`
- `tests/test_alert_receiver.py`

The correlation-window slice subsequently added:

- `ml/state/correlation_window.py`
- `tests/test_correlation_window.py`

### Redis client configuration

The Redis client reads these environment variables:

| Variable | Default / configured value |
|---|---|
| `REDIS_HOST` | `localhost` in the client |
| `REDIS_PORT` | `6379` |
| `REDIS_DB` | `0` |
| `REDIS_PASSWORD` | Optional |
| Connection timeout | 5 seconds |
| Socket timeout | 5 seconds |

The client decodes responses as strings and includes a connection check using Redis `PING`.

Inside Docker Compose, the alert receiver uses the Redis service hostname rather than `localhost`.

The `alert-receiver` service configuration includes:

```yaml
REDIS_HOST: "redis"
REDIS_PORT: "6379"
REDIS_DB: "0"
REDIS_DEDUP_TTL_SECONDS: "300"
```

The receiver depends on the PostgreSQL and Redis services.

Redis is not published to the host merely for this integration. Other services should use the appropriate Docker network and service hostname.

## 12. P19 feature A — Alert-delivery deduplication

### Purpose

Prevent repeated deliveries of the same alert identity during a configured time window.

This reduces duplicate persistence and repeated processing when alert notifications are delivered more than once.

### Implementation

File:

`ml/state/deduplication.py`

Tests:

`tests/test_deduplication.py`

The deduplication identity is derived using SHA-256 from the following alert fields:

- `fingerprint`
- `status`
- `startsAt`
- `endsAt`

The resulting key is placed under the Redis prefix:

`aegis:dedup:alert:`

A claim is acquired using Redis `SET` with:

- `NX`: only claim if the key does not already exist.
- `EX`: set an expiration time on the claim.

The default TTL is 300 seconds, configurable through:

`REDIS_DEDUP_TTL_SECONDS`

The implementation also supports releasing an acquired claim when persistence fails.

### Receiver workflow

The alert receiver uses Redis and PostgreSQL together.

The intended sequence is:

1. Receive the alert notification.
2. Attempt to claim the alert's delivery identity in Redis.
3. If an existing claim is found, treat the delivery as a duplicate.
4. If a claim is acquired, proceed with database persistence.
5. If persistence fails, release the Redis claim so that a later delivery can be retried.
6. Allow Redis failures to surface as an HTTP 500 response rather than silently pretending deduplication succeeded.

The identity includes alert status, so a firing notification and a resolved notification have different identities.

This is delivery deduplication, not permanent exactly-once processing. The TTL limits how long a claim remains active, and failures between systems still need to be understood in the context of the receiver's workflow.

### Validation

The following deduplication tests were reported as passing:

- New alert claim succeeds.
- Duplicate claim is rejected.
- Firing and resolved identities differ.
- Non-positive TTL values are rejected.

Additional receiver and Redis client tests were also included in the P19 test suite.

### Limitations

- The claim is temporary and expires after its TTL.
- Redis deduplication does not itself guarantee exactly-once processing across Redis and PostgreSQL.
- This feature should not be described as a complete cooldown or rate-limiting implementation.

## 13. P19 feature B — Correlation-window storage

### Purpose

Store recent signals temporarily in Redis, grouped by host, so that a later correlation workflow can retrieve signals inside a configured time window.

This is an implementation of the storage primitive for correlation, not the entire correlation pipeline.

### Implementation

File:

`ml/state/correlation_window.py`

Tests:

`tests/test_correlation_window.py`

The module uses the P17 signal types and serialization model from:

`ml/correlation/engine.py`

It provides functionality to:

- Derive Redis keys for a host's signals.
- Derive a corresponding payload-hash key.
- Serialize signals into JSON.
- Deserialize JSON back into `Signal` objects.
- Store signal timestamps in a Redis sorted set.
- Store signal payloads in a Redis hash.
- Remove expired signals from both structures.
- Retrieve signals within the requested window.
- Expire idle host state.

### Redis data structures

The sorted-set key prefix is:

`aegis:correlation:host:`

For each host, the module maintains:

1. A sorted set of signal IDs, scored by the signal's `occurred_at` timestamp.
2. A hash containing serialized signal payloads keyed by signal ID.

The payload includes:

- Signal type
- Name
- Occurrence timestamp
- Severity
- Host
- Source
- Message
- Metadata
- Signal ID

The sorted-set member is the signal ID. Reusing a signal ID updates its existing member and payload rather than creating a second member.

### Window behavior

The default correlation-window duration is 300 seconds (five minutes).

The module includes a configuration reader using:

`REDIS_CORRELATION_WINDOW_SECONDS`

Non-positive configured values are rejected.

When a signal is stored, the module:

1. Validates the requested window duration.
2. Requires the supplied `now` value, when provided, to be timezone-aware.
3. Normalizes the current time to UTC.
4. Adds the signal ID and occurrence timestamp to the sorted set.
5. Stores the serialized payload in the hash.
6. Removes entries older than the cutoff from both structures.
7. Sets expiration on both Redis keys.
8. Returns the remaining signals inside the window.

### Important configuration caveat

The current `store_signal()` function has an explicit `window_seconds` parameter whose default is `DEFAULT_WINDOW_SECONDS`.

The environment-reading helper `correlation_window_seconds()` exists, but `store_signal()` does not automatically call it when the caller omits the parameter.

Therefore, do not assume that setting `REDIS_CORRELATION_WINDOW_SECONDS` automatically changes every call to `store_signal()`. A future caller must explicitly read and pass the configured value, or the implementation must be deliberately revised.

This is a known configuration detail, not a reason to reopen P19 by itself.

### Validation

The following 11 correlation-window tests passed:

- Default window is five minutes.
- Expired signals are removed from the index and payloads.
- Host keys are isolated by host.
- Empty hosts are rejected.
- Non-positive configured windows are rejected.
- Reusing a signal ID updates the existing member.
- Signal serialization round-trips correctly.
- Naive current timestamps are rejected.
- Non-positive requested windows are rejected.
- Signal IDs are used as sorted-set members.
- A window can be explicitly configured.

A real Redis integration test was also reported as successful. It verified that expired signals were pruned, duplicate IDs updated their payloads, recent signal types coexisted, and sorted-set and payload counts remained consistent. Temporary test keys were deleted afterward.

### Limitations

- This module is not yet wired into the correlation engine or API.
- It stores temporary signals; PostgreSQL remains the durable source of truth.
- Redis operations are not currently implemented as a single atomic multi-operation transaction.
- Future timestamps are not explicitly excluded from retrieval.
- The window configuration helper is not automatically applied by `store_signal()`.

These limitations must be considered before using this module as a complete production correlation workflow.

## 14. P19 integration boundaries

The two features serve distinct responsibilities.

**Alert deduplication** prevents repeated processing of the same alert delivery within a temporary claim period.

**Correlation-window storage** retains recent signals so that a future correlation workflow can gather related observations by host and time.

Neither feature replaces the P17 correlation engine.

The existing correlation engine's grouping behavior must be preserved unless there is an explicit, tested design change. In particular, the engine groups eligible signals relative to the first signal in a group; it must not silently be changed into a sliding or consecutive-window algorithm.

The P19 storage primitive is not yet connected to that engine, and the API layer has not yet been implemented.

## 15. P19 validation summary

Reported validation checkpoints:

- Four initial deduplication-specific tests passed.
- Redis client tests were added.
- Receiver tests were updated for Redis-backed deduplication.
- Eleven correlation-window tests passed.
- A real Redis integration check passed.
- The full test suite passed 47 tests with zero failures before the correlation-window slice was committed.
- `git diff --check` was clean.
- After the correlation-window tests passed, only the two intended files were untracked.

The 47-test result was obtained before committing the two correlation-window files, but after their tests and real Redis integration checks had been performed. Do not imply that the complete 47-test suite was rerun after the final commit unless that is verified.

## 16. P19 Git history

The relevant commits are:

| Commit | Message | Purpose |
|---|---|---|
| `438bbf7` | `working on p19: integrating Redis` | Initial Redis client and alert-deduplication slice |
| `7219775` | `added window corrolation to redis` | Redis correlation-window storage and tests |

The latest confirmed state is:

```text
7219775 (HEAD -> main, origin/main, origin/HEAD) added window corrolation to redis
438bbf7 working on p19: integrating Redis
e755b7e p18: postgres integration_2
```

The user ran `git status --short && git log -3 --oneline`. The status output was empty, indicating that the working tree was clean. Local `main` and `origin/main` both pointed to `7219775`.

The second P19 commit changed two files, adding 271 lines:

- `ml/state/correlation_window.py`
- `tests/test_correlation_window.py`

Both P19 commits were pushed to GitHub.

No uncommitted work was reported after the push.

## 17. Explicit P19 scope closure

P19 is considered closed for the current project schedule.

Implemented and included in the closed scope:

- Redis client/configuration integration.
- Alert-delivery deduplication with temporary claims and claim release on persistence failure.
- Per-host temporary correlation-window signal storage.
- Tests for these behaviors.

Intentionally deferred:

- Alert cooldowns.
- Rate limiting.
- General-purpose caching.
- Connecting correlation-window storage to the correlation engine/API.
- Further Redis atomicity or configuration refinements unless required by later integration.

Do not mark these deferred capabilities as implemented in project documentation, a CV, or future handoff reports.

The correct description is: **P19 was closed with intentionally reduced scope after implementing Redis-backed alert deduplication and temporary correlation-window storage.**

---

# PART III — Current State and Next Steps

## 18. Confirmed current repository state

As of the latest report:

- Repository: `~/Projects/AegisMonitor-AI`
- Branch: `main`
- Local and remote HEAD: `7219775`
- Working tree: clean
- P18 PostgreSQL checkpoint: `e755b7e`
- P19 initial Redis checkpoint: `438bbf7`
- P19 correlation-window checkpoint: `7219775`

No further command or file inspection has been performed as part of this report. If implementation details beyond those recorded here are needed, inspect the current repository rather than inventing missing facts.

## 19. Next milestone — P20 FastAPI correlation/API layer

P20 is the next milestone.

The intended direction is to expose the existing correlation workflow through FastAPI, reusing:

- The P17 correlation engine.
- The P18 PostgreSQL repository and persistence capabilities.
- The P19 Redis deduplication functionality where appropriate.
- The P19 correlation-window storage when integration is deliberately implemented.

The next milestone should not assume that the current repository already contains a `fastapi-ai/` directory or that a complete correlation API exists. A prior repository inspection found no `fastapi-ai/` directory.

Before implementation:

1. Inspect the actual repository structure and roadmap.
2. Identify the existing FastAPI applications and entry points.
3. Inspect the P17 engine's public interface and P18 repository methods.
4. Define one minimal API vertical slice.
5. Implement and test that slice before expanding the API.

Avoid modifying the Isolation Forest model or saved threshold as part of this work.

## 20. Instructions for future ChatGPT sessions

When this report is provided as context:

- Treat P18 as a committed PostgreSQL persistence integration with documented scope limitations.
- Treat P19 as closed with reduced scope, not as an unfinished checklist that must be completed immediately.
- Remember that alert deduplication is implemented and committed.
- Remember that Redis correlation-window storage is implemented and committed but not yet wired into the correlation engine/API.
- Preserve PostgreSQL as the durable source of truth.
- Preserve the existing P17 correlation engine behavior.
- Do not claim that log-signature relationship persistence, cooldowns, rate limiting, caching, or the full correlation API are implemented.
- Do not ask the user to redo already-confirmed P18/P19 implementation work.
- Do not commit or push without explicit permission.
- Continue with P20 only when the user is ready, using the repository's actual current state as the authority.

**End of report.**