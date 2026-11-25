# Limitations

This repository is a credible engineering demonstration, not a claim of full production readiness.

## Demo data and integrations

- The public demo uses seeded sample records in a non-production workspace.
- `INTEGRATION_MODE=mock` is the default path and performs no external calls.
- Live HubSpot, Gmail, and Google Sheets adapters are implemented, including OAuth URL generation, token exchange, refresh helpers, idempotency checks, and verification reads.
- Live adapters are covered with fake HTTP tests only. No real provider account, OAuth grant, or external write was available during development.
- Mock integrations must not be represented as live integrations.

## LLM behavior

- `AGENT_MODE=deterministic` is the default and the path used by tests and CI.
- `AGENT_MODE=llm` is optional and requires `LLM_API_KEY`.
- LLM output is sanitized and constrained to copy/intent suggestions; it cannot change protected action fields.
- No live LLM evaluation was performed without a credential. The live test is opt-in and skipped by default.

## Deployment posture

- The API service runs `alembic upgrade head` before startup.
- A Celery worker definition exists, but the demo Render free plan does not support deploying it.
- Production uses `CELERY_TASK_ALWAYS_EAGER=false`, so queued executions require a running worker.
- Local Docker Compose includes a worker and is the recommended way to demonstrate queued execution.
- Git auto-connect is not configured for the demo frontend; deployments are managed explicitly.

## Scope not yet implemented

- No advanced observability stack, alerting, SLOs, or distributed tracing.
- No rate limiting, fine-grained invitation management UI, or organization switcher.
- No provider webhook ingestion or continuous CRM synchronization.
- No real customer data, production billing, or tenant onboarding automation.

## What is verified

- Backend lint and tests pass.
- Frontend lint, typecheck, and production build pass.
- Database migrations upgrade from base through `0001_initial` and `0002_oauth_and_execution_safety`.
- Demo frontend and API health endpoints respond successfully.
- The same-origin API proxy supports an end-to-end demo login request.
