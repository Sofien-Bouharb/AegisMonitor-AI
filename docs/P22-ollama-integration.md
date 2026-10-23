# P22 — Local Ollama / LLM Integration

**Date:** 2026-10-23  
**Project:** AegisMonitor AI  
**Repository:** `~/Projects/AegisMonitor-AI`  
**Milestone status:** Implemented and validated; changes remain uncommitted and unpushed.

## Objective

Add a minimal API integration with a locally hosted Ollama model. This milestone establishes text generation as a building block for P23; it does **not** yet perform incident analysis or automatically send monitoring context to the model.

## Architecture

- **Model runtime:** Ollama running locally on the Fedora host.
- **Model:** `llama3.1:8b`.
- **HTTP client:** `httpx`, already present in `requirements.txt` (`httpx>=0.27,<1`).
- **API:** Existing FastAPI service, `correlation-api`, exposes `POST /api/v1/ai/generate`.
- **Deployment:** Docker Compose `ai` and `full` profiles include the API service.
- **Core functionality:** Local/self-hosted; no cloud LLM provider is required.

## Implementation references

| File | Responsibility |
|---|---|
| `ml/api/ollama_client.py` | Small HTTP client for Ollama's `/api/generate` endpoint; validates inputs and rejects malformed/empty responses. |
| `ml/api/app.py` | `GenerationRequest` schema and `POST /api/v1/ai/generate` endpoint; maps local generation failures to HTTP 503. |
| `tests/test_ollama_client.py` | Unit tests for successful generation, transport errors, invalid JSON, missing output, blank prompt, and invalid timeout. |
| `tests/test_api.py` | API tests for success, safe 503 handling, blank prompts, and forbidden extra fields. |
| `docker-compose.yml` | Configures `OLLAMA_BASE_URL` and `OLLAMA_MODEL` for `correlation-api`. |
| `requirements.txt` | Existing `httpx` dependency; no new package was required. |

## API contract

### `POST /api/v1/ai/generate`

Request:

```json
{
  "prompt": "Explain what sustained high CPU usage may indicate in two concise sentences."
}
```

Successful response (`200 OK`):

```json
{
  "model_output": "Generated text from the configured local model."
}
```

Validation and failure behavior:

- `prompt` is required, must contain non-whitespace text, and is limited to 12,000 characters.
- Unknown request fields are rejected.
- A failed or invalid Ollama response is surfaced as a safe `503 Service Unavailable` response.
- The low-level client raises `OllamaError` rather than exposing transport details to API callers.

The endpoint currently accepts a user-supplied prompt. P23 is responsible for assembling bounded, relevant monitoring context and defining the incident-analysis response contract.

## Runtime configuration

The Compose service configures:

```yaml
OLLAMA_BASE_URL: "http://172.18.0.1:11434"
OLLAMA_MODEL: "llama3.1:8b"
```

The host's Ollama service is bound to the Docker bridge gateway address `172.18.0.1:11434`, allowing the container to reach it. The default client fallback is `http://localhost:11434`; inside a container, `localhost` refers to that container, so deployment configuration must override it.

**Deployment caveat:** `172.18.0.1` is the currently verified Docker network gateway, not a universally stable address. If the Compose network is recreated with a different subnet/gateway, update the Ollama bind/configuration accordingly. Ollama is not exposed on the host's Wi-Fi interface in the current setup. Containers with network reachability to that listener can call it; this is not an authentication boundary.

## Validation performed

- `python -m unittest discover -s tests -v` — **99 tests passed**.
- `docker compose --profile ai config --quiet` — passed.
- `git diff --check` — passed.
- Rebuilt and started the API:
  `docker compose --profile ai up -d --build correlation-api`
- Live request to `POST http://localhost:8000/api/v1/ai/generate` returned generated text with **HTTP 200**.
- A Starlette deprecation warning about `httpx` and `TestClient` was observed; it did not fail tests and was not addressed in this milestone.

## Scope and limitations

- P22 proves the local model can be called through the FastAPI service; it does not establish that generated output is factually correct.
- No Prometheus metrics, Loki logs, Redis state, or PostgreSQL records are automatically included in generation requests yet.
- No incident is created, confirmed, or persisted by this endpoint.
- Generated text must not be treated as authoritative telemetry or as proof that an Isolation Forest candidate is a confirmed incident.
- No model retraining, threshold change, or cloud dependency was introduced.
- P22 changes have **not** been committed or pushed.

## Next milestone — P23

Implement AI-assisted incident analysis using the existing structured monitoring context. First inspect the current context endpoint and its response shape, then agree on the smallest API contract. The analysis should cite only supplied context, clearly distinguish observed facts from hypotheses, avoid inventing metrics/logs, and provide cautious actionable recommendations. Preserve the distinction between an anomaly candidate and a verified incident.
