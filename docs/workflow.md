# Workflow

This document traces one neglected-lead follow-up from detection to verification. The same path applies to CRM tasks and CRM updates with different adapter methods.

## End-to-end trace

1. **Detect pipeline risk.** `GET /api/v1/dashboard/pipeline-risks` maps to `backend/app/api/v1/dashboard.py:pipeline_risks`, which calls `backend/app/services/dashboard.py:get_pipeline_risks` with the active `organization_id`.

2. **Create an agent task.** `POST /api/v1/agent/tasks` maps to `backend/app/api/v1/agent.py:create_task`, which calls `backend/app/services/agent.py:create_task`. It creates an `AgentTask`, emits a `queued` event, writes an audit event, and dispatches the run.

3. **Dispatch the run.** `backend/app/workers/dispatch.py:dispatch_agent_task` uses eager execution when configured, otherwise Celery. `backend/app/workers/tasks.py:run_agent_task` calls `backend/app/services/agent.py:run_task_sync`.

4. **Run the LangGraph workflow.** `run_task_sync` builds `AgentState` from `backend/app/agent/state.py` and invokes `backend/app/agent/graph.py:build_graph`. The graph transitions through `classify_intent`, `retrieve_context`, `investigate`, `recommend`, `persist`, and `finalize`. Each transition emits an `AgentTaskEvent`.

5. **Investigate with evidence.** `backend/app/agent/tools.py` provides deterministic investigation summaries and action drafting. The graph produces findings such as `neglected_lead`, `missing_activity_data`, `duplicate_records`, and `untrusted_instruction_detected`, each with evidence and priority.

6. **Draft a bounded action.** `backend/app/agent/tools.py:create_action` builds the proposal. With `AGENT_MODE=llm`, `_llm_draft_recommendations` may update copy, but `safe_llm_action` and `backend/app/schemas/actions.py:validate_action_payload` prevent changes to target, provider, action type, lead, external ID, risk, or protected properties.

7. **Persist recommendations and approvals.** The `persist` node writes `Recommendation` rows and pending `Approval` rows. Each approval stores the action payload and `backend/app/core/hashing.py:action_hash` as a canonical hash.

8. **Approve with human authorization.** `GET /api/v1/approvals` and `POST /api/v1/approvals/{id}/approve` use `backend/app/api/v1/approvals.py`. `backend/app/services/approval.py` checks approver role, organization scope, pending status, expiry, expected hash, payload schema, lead targeting, and integration connectivity.

9. **Create an idempotent execution.** `backend/app/services/approval.py:approve` creates an `ActionExecution` with key `approval:{approval_id}:{action_hash}`. If an execution with that key already exists, the existing record is returned instead of creating a duplicate.

10. **Dispatch execution.** `backend/app/workers/dispatch.py:dispatch_execution` routes to `backend/app/workers/tasks.py:execute_action_task`, which calls `backend/app/services/execution.py:execute_action_sync`.

11. **Execute through an adapter.** `_execute` revalidates the approval, recommendation, integration, tenant, provider, and expiry. `_call_adapter` decrypts credentials, selects a mock or live adapter through `backend/app/integrations/registry.py:get_adapter`, checks the connection, executes the action, and persists refreshed credentials when returned.

12. **Verify the side effect.** Each adapter implements `verify_action`. For email, `send_email` uses a deterministic RFC822 message ID and the adapter reads the draft or sent message. For HubSpot tasks and CRM updates, the adapter reads back the created or updated resource.

13. **Record the outcome.** `backend/app/services/execution.py:_execute` marks the execution `verified` or `failed`. `ExternalTimeoutError` produces `uncertain`; other errors produce `failed`. Audit events record the transition.

14. **Handle uncertainty safely.** `POST /api/v1/executions/{id}/retry` calls `backend/app/services/execution.py:retry_execution`. It first attempts `_reconcile_uncertain` using stored provider references. If reconciliation cannot confirm the action, replay requires `acknowledge_uncertain=true`.

## Trace map

| Concern | File |
| --- | --- |
| Risk detection | `backend/app/services/dashboard.py` |
| Agent task API and state | `backend/app/services/agent.py`, `backend/app/agent/state.py` |
| Workflow nodes | `backend/app/agent/graph.py` |
| Tooling and safe drafting | `backend/app/agent/tools.py` |
| Action schema | `backend/app/schemas/actions.py` |
| Approval controls | `backend/app/services/approval.py` |
| Execution and verification | `backend/app/services/execution.py` |
| Adapter selection | `backend/app/integrations/registry.py` |
| Mock adapters | `backend/app/integrations/mock_*.py` |
| Live adapters | `backend/app/integrations/live_*.py` |
| Auth and tenant context | `backend/app/core/deps.py` |
| Audit records | `backend/app/services/audit.py` |

## Tests covering the trace

- `backend/tests/test_agent_workflow.py`
- `backend/tests/test_security.py`
- `backend/tests/test_phase1_security.py`
- `backend/tests/test_phase2_integrations.py`
- `backend/tests/test_phase3_llm.py`
- `backend/tests/test_integrations.py`
- `backend/tests/test_evals.py`
