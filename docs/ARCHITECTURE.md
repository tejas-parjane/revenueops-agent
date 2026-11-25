# Architecture

## Overview

RevenueOps Agent is a tenant-scoped FastAPI application with a React frontend. It investigates revenue pipeline records, stores evidence-backed findings, proposes actions, and requires human approval before any external side effect.

Current deployed demo:

- Frontend: `https://frontend-eight-kappa-mvu9los0gx.vercel.app/`
- API: `https://revenueops-api-8iwn.onrender.com/api/v1`
- Health: `https://revenueops-api-8iwn.onrender.com/health`

## Request flow

1. Browser calls same-origin `/api/v1/*`.
2. Vercel function `frontend/api/[...path].js` forwards `/api/*` to `${BACKEND_URL}/api/*`.
3. FastAPI dependencies authenticate the JWT and resolve the active organization membership.
4. Services query only rows scoped by `organization_id`.
5. Agent runs are persisted as `AgentTask` and `AgentTaskEvent` rows.
6. Findings and recommendations are persisted before any approval exists.
7. Each recommendation creates a pending `Approval` with a canonical action hash.
8. Approval validates the payload against a strict schema; edits cannot change target, provider, action type, lead, external ID, risk, or CRM properties.
9. Approval creates an `ActionExecution` with a deterministic idempotency key.
10. The worker or eager dispatcher calls the selected adapter and verifies the external reference.
11. Execution status becomes `verified`, `failed`, or `uncertain`. Uncertain executions require explicit acknowledgement before replay.

## Backend components

- `app/api/v1`: HTTP routes for auth, organizations, leads, agent tasks, approvals, executions, dashboard, and integrations.
- `app/services`: tenant-scoped business logic.
- `app/agent/graph.py`: LangGraph workflow: classify intent, retrieve context, investigate, recommend, persist, finalize.
- `app/agent/tools.py`: deterministic investigation tools and safe action drafting.
- `app/agent/llm.py`: optional OpenAI-compatible JSON client.
- `app/integrations`: mock and live HubSpot, Gmail, and Google Sheets adapters, OAuth helpers, HTTP helper, and provider registry.
- `app/models/entities.py`: SQLAlchemy models including `OAuthState` and `ActionExecution`.
- `alembic/versions`: `0001_initial` plus `0002_oauth_and_execution_safety`.

## Modes

- `INTEGRATION_MODE=mock`: no external network calls; seeded demo integrations remain mock.
- `INTEGRATION_MODE=live`: provider OAuth URLs, token exchange, refresh, and API calls are enabled; credentials are required.
- `INTEGRATION_MODE=auto`: each provider is live only when its OAuth config exists, otherwise mock.
- `AGENT_MODE=deterministic`: rule-based classification, findings, and action drafting.
- `AGENT_MODE=llm`: LLM-assisted classification and copy drafting. All output is sanitized and validated; invalid output falls back deterministically.

## Safety boundaries

- OAuth state is random, hashed at rest, provider/organization/user/redirect-bound, expiring, and single-use.
- Live callback endpoint is public but can only consume a persisted state row.
- Mock and live OAuth state flows are separated.
- Action payloads are validated on approval, execution, and uncertain reconciliation.
- External operations are verified after execution when a provider reference is available.
- Uncertain executions are reconciled from stored references before any replay.
- Raw provider content is sanitized before entering prompts or action text.

## Deployment state

- Render hosts Postgres, Redis, and the API web service.
- The worker definition exists but is not deployed because the Render free plan rejects worker services.
- Production uses `CELERY_TASK_ALWAYS_EAGER=false`, so queued executions require a running worker.
- Vercel Git auto-connect is blocked by GitHub app permissions; current deploy workflow is manual `vercel --prod`.
- Vercel needs `BACKEND_URL` and `NODEJS_HELPERS=0`; deployment protection is disabled for the public demo domain.

## Documentation

- `docs/IMPLEMENTATION_PLAN.md`: phase plan and acceptance criteria.
- `docs/IMPLEMENTATION_PROGRESS.md`: completed work, verification commands, and live-verification gaps.
- `docs/INTEGRATION_SETUP.md`: credentials and OAuth setup.
- `docs/AGENT_EVALUATION.md`: evaluation cases and scoring.
