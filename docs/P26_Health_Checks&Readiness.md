# P26 — Health Checks and Readiness

**Project:** AegisMonitor AI  
**Milestone:** P26  
**Status:** Completed  
**Scope:** Docker Compose health checks and service startup dependencies

## 1. Objective

Improve the reliability and observability of the local AegisMonitor AI stack by adding container health checks to key services and ensuring that dependent services wait for PostgreSQL and Redis to become healthy before starting.

The implementation follows the existing MVP-first approach without introducing additional containers or unnecessary dependencies.

## 2. Implementation

### 2.1 PostgreSQL

Added a health check using `pg_isready` to verify that PostgreSQL is accepting connections.

- **Interval:** 10 seconds
- **Timeout:** 5 seconds
- **Retries:** 5
- **Start period:** 10 seconds

The check uses the configured PostgreSQL username and database.

### 2.2 Redis

Added a health check using `redis-cli ping` to verify that Redis responds to commands.

- **Interval:** 10 seconds
- **Timeout:** 3 seconds
- **Retries:** 5
- **Start period:** 5 seconds

### 2.3 FastAPI Correlation API

Added a health check that sends an HTTP request to the existing `/health` endpoint at `127.0.0.1:8000`.

- **Interval:** 30 seconds
- **Timeout:** 5 seconds
- **Retries:** 3
- **Start period:** 15 seconds

This verifies that the API endpoint responds successfully. It is a lightweight liveness check and does not independently verify every downstream dependency.

### 2.4 Prometheus

Added a health check using Prometheus's native readiness command:

`promtool check ready --url=http://localhost:9090`

- **Interval:** 30 seconds
- **Timeout:** 5 seconds
- **Retries:** 3
- **Start period:** 15 seconds

This checks whether Prometheus reports itself ready to serve requests.

### 2.5 Grafana

Added a health check against Grafana's built-in health endpoint:

`http://127.0.0.1:3000/api/health`

The check uses `wget` inside the container.

- **Interval:** 30 seconds
- **Timeout:** 5 seconds
- **Retries:** 3
- **Start period:** 15 seconds

### 2.6 Service Startup Dependencies

Updated `depends_on` for the following services:

- `alert-receiver`
- `correlation-api`

Both now wait for PostgreSQL and Redis to reach the `healthy` state before starting.

This improves startup ordering, although it does not guarantee that dependencies will remain available after startup.

### 2.7 Loki

Loki's `/ready` endpoint was checked separately. It initially returned HTTP 503, but a subsequent check returned HTTP 200 with the response `ready`.

The `grafana/loki:3.7.8` image does not provide `/bin/sh` or `/usr/bin/wget` at the tested paths. A Docker health check was therefore omitted rather than modifying the image solely to add a probe utility.

Loki readiness can be validated separately using:

`curl -i http://localhost:3100/ready`

## 3. Validation

The following checks were performed:

| Validation                                      | Result                       |
| ----------------------------------------------- | ---------------------------- |
| `docker compose --profile ai config --quiet`    | Passed                       |
| `docker compose --profile dev config --quiet`   | Passed                       |
| `docker compose --profile full config --quiet`  | Passed                       |
| PostgreSQL health check                         | Passed                       |
| Redis health check                              | Passed                       |
| FastAPI `/health` endpoint                      | HTTP 200                     |
| Prometheus readiness check                      | Passed                       |
| Grafana `/api/health` endpoint                  | HTTP 200                     |
| Docker health status for Prometheus and Grafana | Healthy                      |
| Docker health status for Correlation API        | Healthy                      |
| Loki `/ready` endpoint                          | HTTP 200 on subsequent check |
| `git diff --check`                              | Passed                       |
| Modified files                                  | `docker-compose.yml` only    |

## 4. Design Decisions

- Used existing health and readiness endpoints where possible.
- Avoided adding custom images or helper containers solely for health checks.
- Kept PostgreSQL and Redis as explicit startup dependencies for services that require them.
- Did not make Loki a dependency of the AI profile; log context remains an optional capability.
- Kept the FastAPI check lightweight rather than turning it into a comprehensive dependency diagnostic.
- Did not change the Isolation Forest model, its threshold, or its feature configuration.

## 5. Limitations

- Docker health status does not automatically restart a container merely because its health check reports `unhealthy`; restart policies primarily react to container termination.
- The FastAPI `/health` endpoint does not guarantee that PostgreSQL, Redis, or Ollama is operational.
- Loki has no Docker-level health check in this milestone. Its readiness endpoint was verified separately.
- Health checks improve startup coordination and failure visibility but do not replace application-level retries, timeouts, or runtime recovery.

## 6. Outcome

P26 adds lightweight health checks to PostgreSQL, Redis, FastAPI, Prometheus, and Grafana, and improves startup coordination for the alert receiver and correlation API.

Compose configuration validation passed for all three profiles: `ai`, `dev`, and `full`. The changes are limited to `docker-compose.yml`, and the diff passes whitespace/error checks.

**P26 is considered complete based on the implementation and validation performed.**

## 7. Next Milestone

**P27 — Final Refinements**

Proceed with the remaining roadmap refinements, prioritizing the highest-value improvements and avoiding unnecessary scope expansion.
