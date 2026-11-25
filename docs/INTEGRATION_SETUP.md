# Integration Setup

## Modes

Set `INTEGRATION_MODE` on the API and worker:

- `mock`: keep demo behavior and ignore provider OAuth credentials.
- `live`: require complete OAuth config for every provider that will be used.
- `auto`: use live config when present, otherwise fall back to mock for that provider.

The UI shows `Mock data` or `Live OAuth` on each integration card. Mock mode never calls external APIs.

## Callback paths

For live provider redirects, register an absolute callback URL matching the backend deployment:

- HubSpot: `https://revenueops-api-8iwn.onrender.com/api/v1/integrations/hubspot/oauth/callback`
- Gmail: `https://revenueops-api-8iwn.onrender.com/api/v1/integrations/gmail/oauth/callback`
- Google Sheets: `https://revenueops-api-8iwn.onrender.com/api/v1/integrations/google_sheets/oauth/callback`

The callback endpoint is public because the provider redirects the browser there. It consumes a one-time `OAuthState` row that was created by an authenticated `/connect` call.

## Flow

1. Sign in and call `GET /api/v1/integrations/{provider}/connect` with the Bearer token.
2. The API creates a one-time state row and returns `authorization_url`, `state`, `callback_url`, and `mode`.
3. In live mode, redirect the browser to `authorization_url`.
4. The provider redirects to `/api/v1/integrations/{provider}/oauth/callback?code=...&state=...`.
5. The API consumes the state, exchanges the code, encrypts tokens, and stores a live integration.
6. `Sync now` calls the live adapter and persists refreshed tokens if the provider rotates them.

Mock mode uses the authenticated `GET /api/v1/integrations/{provider}/callback?state=...&external_account_id=...` endpoint instead.

## HubSpot

Create a HubSpot app with these scopes:

- `crm.objects.contacts.read`
- `crm.objects.deals.read`
- `tasks.write`

Set:

```text
HUBSPOT_CLIENT_ID=
HUBSPOT_CLIENT_SECRET=
HUBSPOT_REDIRECT_URI=https://revenueops-api-8iwn.onrender.com/api/v1/integrations/hubspot/oauth/callback
```

Live adapter behavior:

- `fetch_leads`: reads contacts and maps name, email, company, deal value, stage, owner, notes, and last-modified timestamp.
- `create_task`: creates a HubSpot task and checks for an existing task by idempotency key before creation.
- `update_record`: patches a contact.
- `verify_action`: reads the created task or updated contact.

## Gmail

Create a Google OAuth client with these scopes:

- `https://www.googleapis.com/auth/gmail.readonly`
- `https://www.googleapis.com/auth/gmail.compose`

Set:

```text
GMAIL_CLIENT_ID=
GMAIL_CLIENT_SECRET=
GMAIL_REDIRECT_URI=https://revenueops-api-8iwn.onrender.com/api/v1/integrations/gmail/oauth/callback
```

Live adapter behavior:

- `create_draft`: creates a Gmail draft with a deterministic `Message-ID`.
- `send_email`: checks for an existing sent message by RFC822 message ID before sending.
- `verify_action`: reads the draft or sent message.

## Google Sheets

Create a Google OAuth client with this scope:

- `https://www.googleapis.com/auth/spreadsheets`

Set:

```text
GOOGLE_SHEETS_CLIENT_ID=
GOOGLE_SHEETS_CLIENT_SECRET=
GOOGLE_SHEETS_REDIRECT_URI=https://revenueops-api-8iwn.onrender.com/api/v1/integrations/google_sheets/oauth/callback
GOOGLE_SHEETS_SPREADSHEET_ID=
GOOGLE_SHEETS_RANGE=Pipeline!A:G
```

Expected columns are normalized to lower snake case: `external_id`, `name`, `email`, `company`, `deal_value`, `stage`, `owner`, `last_activity_at`, and `notes`. `create_task` appends a row with an idempotency key; `update_record` updates a matching row when possible.

## Secret handling

- Tokens are encrypted with `TOKEN_ENCRYPTION_KEY`.
- OAuth state stores only a SHA-256 hash of the random state value.
- Do not commit `.env`, OAuth client secrets, tokens, or Vercel/Render credentials.

## Verification status

The live adapters, OAuth URL generation, token exchange, refresh helpers, and verification calls are implemented with local fake HTTP tests. No real HubSpot, Gmail, or Google account was available, so no live OAuth grant or external write was performed.
