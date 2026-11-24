# RevenueOps Agent

Full-stack MVP scaffold for evidence-backed revenue operations investigation with human approval before external actions.

## URLs

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

## Login details

There is no pre-seeded demo account. Create one from the registration page, then sign in with the same email and password.

Open http://localhost:5173/register and use:

- Full name: `Alex Morgan`
- Organization: `Acme Revenue`
- Work email: `admin@example.com`
- Password: `password123`

Then sign in at http://localhost:5173/login with:

- Email: `admin@example.com`
- Password: `password123`

Registration creates the organization, owner user, mock HubSpot/Gmail/Google Sheets integrations, and sample HubSpot leads.

You can also register via API:

```powershell
curl -X POST "http://localhost:8000/api/v1/auth/register" `
  -H "Content-Type: application/json" `
  -d '{"full_name":"Alex Morgan","organization_name":"Acme Revenue","email":"admin@example.com","password":"password123"}'
```

Then log in via API:

```powershell
curl -X POST "http://localhost:8000/api/v1/auth/login" `
  -H "Content-Type: application/json" `
  -d '{"email":"admin@example.com","password":"password123"}'
```

## Run with Docker Compose

Requirements: Docker Desktop with Compose.

From the repository root:

```powershell
docker compose up --build
```

Open http://localhost:5173 and register as described above.

Stop the stack:

```powershell
docker compose down
```

Stop and delete the database volume:

```powershell
docker compose down -v
```

## Run locally without Docker

Requirements: Python 3.12+, Node.js 20+, npm.

### Backend

From `backend/`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Set local SQLite/eager-worker environment variables:

```powershell
$env:DATABASE_URL = "sqlite:///./revenueops_local.db"
$env:CELERY_TASK_ALWAYS_EAGER = "true"
$env:AUTO_CREATE_TABLES = "true"
$env:JWT_SECRET_KEY = "local-development-jwt-secret"
$env:TOKEN_ENCRYPTION_KEY = "local-development-encryption-key"
$env:CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
```

Run migrations and start the API:

```powershell
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

From `frontend/`:

```powershell
npm install
$env:VITE_API_PROXY_TARGET = "http://localhost:8000"
npm run dev
```

Open http://localhost:5173.

## Useful checks

Backend tests and lint, from `backend/`:

```powershell
.\.venv\Scripts\pytest -q
.\.venv\Scripts\ruff check .
```

Frontend checks, from `frontend/`:

```powershell
npm run typecheck
npm run lint
npm run build
```

## Environment

The Docker Compose stack sets development defaults for Postgres, Redis, JWT, encryption, and CORS. For non-Docker runs, copy `.env.example` to `.env` and adjust values as needed.

```powershell
Copy-Item .env.example .env
```

## Deploy to Render + Vercel

Render hosts the API, Celery worker, PostgreSQL, and Redis. Vercel hosts the static frontend and proxies `/api/*` to the Render API.

### 1. Render

The root `render.yaml` Blueprint creates:

- `revenueops-db` PostgreSQL database
- `revenueops-redis` Key Value instance
- `revenueops-api` web service
- `revenueops-worker` background worker

Push the repository to GitHub, then create a Render Blueprint from `render.yaml`. Fill these sync-required secrets in the Render dashboard:

- `JWT_SECRET_KEY`
- `TOKEN_ENCRYPTION_KEY`
- `CORS_ORIGINS` set to your Vercel domain, for example `https://your-app.vercel.app`

The API service runs `alembic upgrade head` before starting, so no manual migration step is needed. Copy the public URL of `revenueops-api`, for example `https://revenueops-api.onrender.com`.

### 2. Vercel

From `frontend/`:

```powershell
vercel login
vercel env add BACKEND_URL production
```

When prompted for `BACKEND_URL`, use the Render API URL without a trailing `/api`, for example `https://revenueops-api.onrender.com`.

Then deploy:

```powershell
vercel --prod
```

`frontend/api/[...path].js` forwards browser requests from `/api/*` to `${BACKEND_URL}/api/*`, so the frontend uses same-origin API URLs and does not expose the Render URL to the browser.
