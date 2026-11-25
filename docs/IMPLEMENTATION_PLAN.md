# RevenueOps Agent Production Implementation Plan

## Scope

This plan covers the production-readiness work for the existing `E:\RevenueOps Agent_FDE` repository. The MVP is already deployed and functional in demo mode:

- Frontend: `https://frontend-eight-kappa-mvu9los0gx.vercel.app/`
- API: `https://revenueops-api-8iwn.onrender.com/api/v1`
- Current source state: pushed through `b619b2c Fix Vercel API proxy`

The implementation must extend the current system, not rewrite it. Live external side effects must remain behind human approval. If real OAuth/LLM credentials are unavailable, the code must expose explicit mock/deterministic mode and the documentation must state the limitation instead of implying live verification.

## Current Architecture

- `backend/` is a FastAPI application with SQLAlchemy 2 models, Alembic migrations, Pydantic v2 schemas, service classes, and Celery workers.
- `backend/app/agent/graph.py` is a deterministic LangGraph workflow: classify intent, retrieve tenant-scoped records, investigate, recommend, persist approvals, finalize.
- `backend/app/integrations/` currently contains mock HubSpot, Gmail, and Google Sheets adapters behind `BaseIntegrationAdapter`.
- Registration seeds connected mock integrations and six HubSpot fixture leads for each new organization.
- `frontend/` is a Vite/React/TypeScript SPA. It uses same-origin `/api/v1` calls; Vercel proxies `/api/*` to Render through `frontend/api/[...path].js`.
- Render hosts PostgreSQL, Redis, the API web service, and a worker definition. The worker is not deployed because the current free plan rejects worker services.
- Tenant isolation is based on `active_organization_id` and `OrganizationMember`.

## Current Weaknesses

1. Integrations are always mock. `register_user()` creates connected mock integrations and the UI calls a local callback URL.
2. OAuth state is a timestamp HMAC (`backend/app/services/integration.py:22-40`) with no organization/user binding, no replay protection, and no public callback path for a real provider redirect.
3. Approval edits accept arbitrary dictionaries. `backend/app/services/approval.py:109-128` only checks type, lead id, and external id.
4. Execution retries can replay non-idempotent external operations after uncertain outcomes. `backend/app/services/execution.py:71-80` retries the whole operation.
5. Tenant checks are incomplete in some internal load paths: approval loading joins leads without checking lead organization; execution loading does not verify that all referenced rows belong to the execution organization.
6. Settings allow development JWT/encryption defaults outside tests. Production currently has secrets set, but the application does not fail closed if secrets are missing.
7. There is no LLM dependency or client. Intent classification, findings, and action text are deterministic templates.
8. There is no evaluation suite, integration setup guide, architecture guide, or production-readiness documentation.
9. `IntegrationSchema` does not tell the UI whether a connection is mock or live.
10. Dashboard endpoints open their own sessions instead of using the request dependency, which weakens testability and consistency.
11. The worker is not running in production, so queued Celery tasks would not execute if `CELERY_TASK_ALWAYS_EAGER=false`.

## Target Architecture

### Request and data flow

1. Browser calls same-origin `/api/v1/*`.
2. Vercel function forwards requests to `${BACKEND_URL}/api/*`.
3. FastAPI dependencies authenticate the JWT and resolve an active tenant membership.
4. Services operate only on rows scoped by `organization_id`.
5. Agent runs are persisted as `AgentTask` + `AgentTaskEvent` rows; findings and recommendations are persisted before any external action.
6. Recommendations become pending `Approval` rows with an `action_hash`.
7. An approver reviews the payload, evidence, provider, risk, and hash. Approval validates the payload against a strict schema.
8. Approval creates a deterministic `ActionExecution` with an idempotency key.
9. Worker or eager dispatcher calls an adapter. The adapter performs the external call and verifies the resulting external reference.
10. Execution status becomes `verified`, `failed`, or `uncertain`. `uncertain` requires reconciliation rather than blind replay.
11. Activity and audit records expose the full chain to the UI.

### Modes

- `INTEGRATION_MODE=mock`: current demo behavior. No external network calls. Explicitly labeled in UI and docs.
- `INTEGRATION_MODE=live`: real OAuth authorization URL, token exchange, refresh, API calls, and verification. Requires provider client credentials and redirect URIs.
- `INTEGRATION_MODE=auto`: live when provider credentials are present, otherwise mock for that provider.
- `AGENT_MODE=deterministic`: current rule-based workflow. Used in tests and when no LLM credentials are configured.
- `AGENT_MODE=llm`: LLM-assisted classification, prioritization, and action drafting, with deterministic validation and fallback. No LLM output can trigger an external action without approval.

## Phase 1: Reliability and Security Hardening

Changes:

- Add strict action payload validation for approve/edit paths.
- Bind approval and execution rows to the organization on every load path.
- Make uncertain executions require explicit reconciliation before retry.
- Replace timestamp HMAC OAuth state with a persisted, one-time, organization/user-bound state record.
- Add production secret validation for JWT and token encryption keys.
- Make dashboard endpoints use `Depends(get_db)`.
- Add tests for edited action validation, cross-tenant approval/execution access, OAuth state replay, and production secret validation.

Acceptance:

- `pytest -q` passes.
- `ruff check .` passes.
- No arbitrary action fields can be approved.
- A state generated for one org/user/provider cannot be used by another.
- An uncertain execution is not silently replayed.

## Phase 2: Real Integration Adapters and OAuth Lifecycle

Changes:

- Add provider OAuth configuration to settings and `.env.example`.
- Add `OAuthState` model and Alembic migration.
- Add public `GET /api/v1/integrations/{provider}/oauth/callback`.
- Keep the existing authenticated mock callback for demo mode.
- Add real HubSpot, Gmail, and Google Sheets adapters using standard-library HTTP calls.
- Add token refresh and expiry handling in encrypted credentials.
- Add `mode` to integration and connect responses.
- Update the Integrations UI to distinguish mock/live and start real OAuth redirects.
- Add adapter tests using monkeypatched HTTP responses.

Acceptance:

- Mock mode still works end-to-end.
- Live mode produces real provider authorization URLs and stores exchanged tokens.
- Sync/action/verification calls are covered by tests with fake HTTP responses.
- Documentation states exactly which credentials are required and which live paths were not verifiable without accounts.

## Phase 3: LLM-Backed LangGraph

Changes:

- Add a small OpenAI-compatible JSON client using standard-library HTTP.
- Add prompt templates that treat retrieved CRM data as untrusted evidence.
- Add tool helpers for neglected leads, duplicates, missing activity, and action drafting.
- Extend `AgentState` with mode/model/tool trace fields.
- Use LLM output only after schema validation and sanitization; fall back to deterministic output on any error.
- Include mode/model metadata in task results and events.

Acceptance:

- Deterministic mode remains fully testable without network access.
- Invalid or injected LLM output cannot bypass action validation.
- `pytest -q` and `ruff check .` pass.

## Phase 4: Evaluation Suite

Changes:

- Add `backend/evals/` cases covering neglected high-value leads, low-value inactive leads, duplicate records, missing activity, prompt injection, and cross-data-source attribution.
- Add a runner and pytest coverage for expected findings, recommendation types, evidence presence, and absence of injected recipients.
- Add optional live LLM evaluation that is skipped unless explicitly enabled with credentials.
- Document scoring, pass/fail criteria, and how to add cases.

Acceptance:

- Evaluation suite passes in deterministic mode.
- Live LLM evaluation is opt-in and never required for CI.
- `docs/AGENT_EVALUATION.md` explains the suite.

## Phase 5: Frontend Workflow Improvements

Changes:

- Show mock/live integration mode and real OAuth connect behavior.
- Send `expected_hash` on approval to prevent stale approvals.
- Add clearer approval detail: lead, evidence, action hash, risk, provider, expiry, and execution result.
- Show execution verification payload, idempotency key, and uncertain status in Activity.
- Add agent mode/model and tool trace visibility in AgentWorkspace.
- Add precise error states for disconnected/expired integrations.

Acceptance:

- `npm run typecheck`, `npm run lint`, and `npm run build` pass.
- Mock demo flow still works.
- Live connect flow redirects to provider authorization when configured.

## Phase 6: Database, Deployment, and Documentation

Changes:

- Add migration `0002_oauth_and_execution_safety.py`.
- Add indexes/constraints that are safe against the existing production database.
- Update `.env.example`, `README.md`, `render.yaml`, and Vercel notes.
- Add `docs/ARCHITECTURE.md`, `docs/INTEGRATION_SETUP.md`, `docs/IMPLEMENTATION_PROGRESS.md`, and `docs/AGENT_EVALUATION.md`.
- Run full backend and frontend verification.
- Document Render worker limitation and Vercel Git auto-connect limitation.

Acceptance:

- Alembic upgrade succeeds from `0001_initial` to `0002`.
- All backend and frontend checks pass.
- Docs accurately describe deployed state, limitations, credentials, and manual steps.
- No secrets are committed.

## Migration Needs

- `oauth_states`: raw state is never stored; store a hash plus provider, organization, user, redirect URI, expiry, and consumption timestamp.
- Index on `oauth_states(state_hash)` for fast one-time lookup.
- Index on `oauth_states(organization_id, provider, expires_at)` for cleanup.
- Consider an index on `leads(organization_id, email)` for duplicate detection.
- Avoid destructive changes to existing production rows.
- Keep `0001_initial` intact because it is already applied in production.

## Credentials and External Access

Required for live integrations:

- `HUBSPOT_CLIENT_ID`, `HUBSPOT_CLIENT_SECRET`, `HUBSPOT_REDIRECT_URI`
- `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REDIRECT_URI`
- `GOOGLE_SHEETS_CLIENT_ID`, `GOOGLE_SHEETS_CLIENT_SECRET`, `GOOGLE_SHEETS_REDIRECT_URI`
- `GOOGLE_SHEETS_SPREADSHEET_ID`, `GOOGLE_SHEETS_RANGE`

Required for LLM mode:

- `LLM_API_KEY`
- `LLM_BASE_URL` default `https://api.openai.com/v1`
- `LLM_MODEL`
- optional `LLM_TEMPERATURE`, `LLM_TIMEOUT_SECONDS`

Not available during this implementation:

- Real HubSpot app credentials and account
- Real Google OAuth client credentials, Gmail account, and Sheets document
- Real LLM API key for live evaluation

These paths will be implemented and tested with local fakes, but docs must not claim live verification.

## Deployment Constraints

- Render free plan cannot run `revenueops-worker`; worker remains undeployed unless the user authorizes a paid plan.
- Current production settings use `CELERY_TASK_ALWAYS_EAGER=false`, so a missing worker means queued tasks would not execute. Production-readiness docs must call this out and provide the paid-worker step.
- Vercel Git auto-connect is blocked by GitHub app/repository permissions. Use manual `vercel --prod` until fixed.
- Vercel needs `BACKEND_URL`, `NODEJS_HELPERS=0`, and disabled deployment protection for the current public demo domain.
- Do not commit `.env`, local Vercel output, browser logs, or credentials.

## Acceptance Summary

- Existing MVP behavior remains intact in mock/deterministic mode.
- Security gaps around approval, execution, and OAuth state are closed.
- Live integration and LLM code paths exist but are explicit, credential-gated, and documented.
- All changes are tested locally after each phase.
- Final docs state what is verified, what is implemented-but-not-live-verified, and what still requires user-supplied credentials or paid infrastructure.
