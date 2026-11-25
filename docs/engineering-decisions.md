# Engineering Decisions

These five decisions are the reliability core of the project.

## 1. Why LangGraph instead of one LLM prompt?

An approval workflow needs explicit state, durable history, and predictable gates. `backend/app/agent/graph.py` models the work as `classify_intent -> retrieve_context -> investigate -> recommend -> persist -> finalize`, with each step emitting an `AgentTaskEvent`. That makes it possible to inspect where a finding came from, retry a failed stage, and test the workflow without an LLM.

The LLM is an optional contributor to classification and action copy, not the control plane. Invalid output is sanitized and falls back to deterministic behavior through `backend/app/agent/tools.py:safe_llm_action` and `backend/app/schemas/actions.py`.

Trade-off: explicit nodes are more code than a single prompt, but they make evidence, approval, and failure handling reviewable.

## 2. Why require human approval?

Sending email, creating CRM tasks, updating CRM properties, and appending spreadsheet rows are external side effects. The system should not perform them merely because a model suggested them.

`backend/app/services/approval.py` requires an authorized approver, pending non-expired approval, expected action hash match, strict payload validation, unaffected protected fields, and a connected provider integration. The UI sends `expected_hash` so an approval cannot silently apply to a changed recommendation.

Trade-off: approval adds a human step, but it creates a clear accountability boundary between recommendation and execution.

## 3. How duplicate execution is prevented

`backend/app/services/approval.py` creates `ActionExecution` with a deterministic key: `approval:{approval_id}:{action_hash}`. `ActionExecution.idempotency_key` is unique in the database. If the same approval is submitted again, the existing execution is returned.

Adapters add provider-side idempotency where possible: Gmail uses a deterministic RFC822 message ID, HubSpot checks for existing tasks by idempotency key, and Sheets checks for matching keys before appending or updating.

Only rate limits are retried. Ambiguous write timeouts are never retried in the initial execution path: `backend/app/services/execution.py:_with_retries` retries `RateLimitError` only, and `ExternalTimeoutError` immediately marks the execution `uncertain`. Competing workers are blocked by `_claim_execution`, an atomic conditional update that claims a `pending` or `failed` execution as `running` before dispatch. `_reconcile_uncertain` then reads stored provider references before any replay; unresolved cases require explicit acknowledgement.

Trade-off: the system may stop for human review more often, but it avoids the worse failure of double-sending or double-writing.

## 4. How tenant data is protected

`backend/app/core/deps.py` resolves the user and active organization from the JWT and membership records. Services filter queries by `organization_id`, including agent tasks, approvals, executions, integrations, dashboard data, leads, and OAuth state.

Approvals and executions are reloaded tenant-scoped at action time, so a valid ID from another organization cannot be approved or retried. OAuth state is also bound to organization, user, provider, and redirect URI, then stored as a hash and consumed once.

Trade-off: scoping checks are repeated at several layers, but authorization does not depend on a single UI or route assumption.

## 5. How execution is verified

An attempted API call is not treated as a successful business outcome. After executing, `backend/app/services/execution.py` calls the adapter's `verify_action` method. The adapter reads back the provider object using a stored reference, such as a Gmail message ID, HubSpot task ID, or Sheets row reference.

The execution becomes `verified` only when that read-back succeeds. Failed verification produces `failed`; ambiguous provider timeouts produce `uncertain`. The response payload, provider reference, status, and audit event are persisted so the UI can show what actually happened.

Trade-off: verification adds provider calls and can surface ambiguous states, but it separates "we called the API" from "the external system confirms the action exists."
