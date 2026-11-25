# Agent Evaluation

The evaluation suite checks the agent's deterministic reasoning and action proposals without network calls or a database.

## Run

From `backend/`:

```powershell
& ".\.venv\Scripts\pytest" -q tests/test_evals.py
```

The full backend test run includes the same cases:

```powershell
& ".\.venv\Scripts\pytest" -q
```

Live LLM evaluation is opt-in. Set `AGENT_MODE=llm` and `LLM_API_KEY`, then run the full pytest command. Without both values, the live test is skipped.

## Cases

- `neglected_high_value_lead`: expects a high-priority neglected-lead finding and an email follow-up with evidence.
- `low_value_inactive_lead`: expects a neglected-lead finding, low priority, and an email follow-up.
- `duplicate_records`: expects duplicate detection and a CRM task.
- `missing_activity`: expects a missing-activity finding and a CRM update.
- `prompt_injection`: expects an untrusted-instruction finding and verifies the injected recipient never becomes an email target.
- `cross_data_source_attribution`: expects findings from both HubSpot and Google Sheets records with matching evidence sources.

## Scoring

Each case produces boolean checks for:

- expected finding types and minimum counts;
- expected priorities;
- expected action types;
- evidence presence;
- forbidden recipients;
- expected evidence sources.

`score = passed checks / total checks`. A case passes only when every check passes.

## Adding a case

1. Add an `EvalCase` to `backend/evals/cases.py`.
2. Use `EvalCase.records` with tenant-like lead dictionaries; no database is required.
3. Add expected findings, action types, and safety constraints.
4. Run the suite and refine the deterministic rules or sanitizer if the case fails.

## Limitations

- Evaluations validate proposed actions, not external side effects.
- LLM output is checked with the same action validation used before approval; it cannot change target, provider, action type, lead, external ID, risk, or CRM properties.
- No real LLM result is required for CI.
