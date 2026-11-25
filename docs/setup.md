# Setup

## Stack

- Python 3.12+, FastAPI, SQLAlchemy, Alembic, Celery
- Node.js 20+, npm, React, TypeScript, Vite
- PostgreSQL and Redis through Docker Compose
- Optional OpenAI-compatible LLM and OAuth provider credentials

## Docker Compose

From the repository root:

```bash
docker compose up --build
```

The UI is served on port `5173`, the API on port `8000`, and API documentation on port `8000/docs`. Register a workspace in the UI; registration seeds sample leads and mock HubSpot, Gmail, and Google Sheets integrations.

Stop the stack:

```bash
docker compose down
```

Delete the database volume when a clean seed is needed:

```bash
docker compose down -v
```

## Environment variables

Copy the template and adjust values:

```bash
cp .env.example .env
```

Key variables:

| Variable | Purpose |
| --- | --- |
| `ENVIRONMENT` | App environment name; production enables strict secret validation |
| `DATABASE_URL` | SQLAlchemy database connection |
| `JWT_SECRET_KEY` | Access token signing secret |
| `TOKEN_ENCRYPTION_KEY` | Encryption key for stored provider tokens |
| `CELERY_BROKER_URL` | Celery broker connection |
| `CELERY_RESULT_BACKEND` | Celery result backend connection |
| `CELERY_TASK_ALWAYS_EAGER` | `true` runs tasks inline; `false` requires a worker |
| `AUTO_CREATE_TABLES` | Development-only schema creation fallback |
| `CORS_ORIGINS` | Allowed browser origins |
| `INTEGRATION_MODE` | `mock`, `live`, or `auto` |
| `AGENT_MODE` | `deterministic` or `llm` |
| `LLM_API_KEY` | Optional LLM credential |
| `HUBSPOT_CLIENT_ID`, `HUBSPOT_CLIENT_SECRET`, `HUBSPOT_REDIRECT_URI` | HubSpot live OAuth |
| `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REDIRECT_URI` | Gmail live OAuth |
| `GOOGLE_SHEETS_CLIENT_ID`, `GOOGLE_SHEETS_CLIENT_SECRET`, `GOOGLE_SHEETS_REDIRECT_URI` | Sheets live OAuth |
| `GOOGLE_SHEETS_SPREADSHEET_ID`, `GOOGLE_SHEETS_RANGE` | Sheets target document and range |

Do not commit `.env`, provider secrets, tokens, dashboard credentials, or real customer data.

## Manual backend run

From `backend/`:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Set the environment values for your database, broker, secrets, CORS origin, and modes. Then run:

```bash
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

For inline execution without a worker, set `CELERY_TASK_ALWAYS_EAGER=true`.

## Manual frontend run

From `frontend/`:

```bash
npm install
npm run dev
```

The Vite dev server proxies API requests to the backend service configured in `frontend/vite.config.ts`.

## Agent and integration modes

`AGENT_MODE=deterministic` is recommended for local evaluation. `AGENT_MODE=llm` enables optional LLM-assisted classification and copy drafting with schema validation and deterministic fallback.

`INTEGRATION_MODE=mock` is the safest demo path. `INTEGRATION_MODE=live` uses real provider APIs. `INTEGRATION_MODE=auto` selects live behavior per provider only when complete credentials are present.

## Live OAuth callbacks

Register absolute callback URLs with each provider using your API domain:

```text
https://<api-domain>/api/v1/integrations/hubspot/oauth/callback
https://<api-domain>/api/v1/integrations/gmail/oauth/callback
https://<api-domain>/api/v1/integrations/google_sheets/oauth/callback
```

Flow:

1. Sign in and call `GET /api/v1/integrations/{provider}/connect` with the Bearer token.
2. The API creates a one-time `OAuthState` row and returns `authorization_url` and `mode`.
3. In live mode, redirect the browser to `authorization_url`.
4. The provider redirects to `/oauth/callback` with `code` and `state`.
5. The API consumes the state, exchanges the code, encrypts tokens, and stores the integration.
6. `Sync now` uses the live adapter and persists refreshed tokens when the provider rotates them.

Mock mode uses the authenticated `/callback` endpoint instead.

## Provider scopes

HubSpot:

- `crm.objects.contacts.read`
- `crm.objects.deals.read`
- `tasks.write`

Gmail:

- `https://www.googleapis.com/auth/gmail.readonly`
- `https://www.googleapis.com/auth/gmail.compose`

Google Sheets:

- `https://www.googleapis.com/auth/spreadsheets`

Expected Sheets columns are normalized to lower snake case: `external_id`, `name`, `email`, `company`, `deal_value`, `stage`, `owner`, `last_activity_at`, and `notes`.

## Deployment notes

The API container runs `alembic upgrade head` before starting. The frontend deployment should serve the static Vite build and rewrite `/api/*` to the API origin so browser requests remain same-origin. A worker process is required when `CELERY_TASK_ALWAYS_EAGER=false`.
