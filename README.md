# Baggage Finder API

FastAPI + PostgreSQL backend for the Baggage Finder mobile app. Implements the
`user` and `baggage` contract in `CRUD_API.md`.

## Tech Stack

| Layer      | Technology                                                   |
| ---------- | ------------------------------------------------------------ |
| Framework  | FastAPI (Python 3.11+)                                       |
| ORM        | SQLAlchemy 2.0 (async)                                       |
| Database   | PostgreSQL (asyncpg); SQLite for tests/quick dev             |
| Migrations | Alembic                                                      |
| Auth       | PyJWT access tokens + rotating opaque refresh tokens, bcrypt |
| Validation | Pydantic v2                                                  |

## Quick Start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env        # then set SECRET_KEY (>= 32 chars)
docker compose up -d db     # local Postgres on 127.0.0.1:5432
alembic upgrade head
uvicorn app.main:app --reload
```

Or run everything in containers: `docker compose up --build` (a one-shot `migrate`
service applies migrations before `api` starts).

The API is served under `API_PREFIX` (default `/api`, matching the app's base URL
`https://baggagefinder.azure-api.net/api/`). Interactive docs are at `/docs` when `DEBUG=true`.

## Configuration

All settings are environment variables (see `.env.example`). Only `DATABASE_URL` and
`SECRET_KEY` are required.

| Variable                      | Description                                     | Default         |
| ----------------------------- | ----------------------------------------------- | --------------- |
| `DATABASE_URL`                | SQLAlchemy async URL                            | (required)      |
| `DATABASE_SSL`                | Require TLS to Postgres (e.g. Azure Database)   | `false`         |
| `SECRET_KEY`                  | JWT signing key, min 32 chars                   | (required)      |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime                           | `30`            |
| `REFRESH_TOKEN_EXPIRE_DAYS`   | Refresh token lifetime                          | `7`             |
| `RESET_TOKEN_EXPIRE_MINUTES`  | Password-reset token lifetime                   | `30`            |
| `API_PREFIX`                  | Path the API is mounted under                   | `/api`          |
| `RATE_LIMIT_PER_MINUTE`       | Per-IP limit on signUp/login/reset endpoints    | `10`            |
| `ALLOWED_ORIGINS`             | Browser CORS origins (JSON array or comma list) | `[]` (CORS off) |
| `DEBUG`                       | Enables `/docs`, `/redoc`, `/openapi.json`      | `false`         |
| `LOG_LEVEL` / `LOG_FORMAT`    | `INFO` / `text` or `json`                       | `INFO` / `text` |

## API

All routes below are relative to `API_PREFIX`. Send `Authorization: Bearer <accessToken>`
on protected routes. IDs are UUID strings.

### Auth

| Method | Path                           | Auth | Notes                                                                 |
| ------ | ------------------------------ | ---- | --------------------------------------------------------------------- |
| POST   | `/signUp`                      | –    | `201` → `{user, accessToken, refreshToken}`                           |
| POST   | `/user/login`                  | –    | Body `{email, password}`; legacy key `passwordHash` also accepted     |
| POST   | `/user/refresh`                | –    | `{refreshToken}` → new pair; the old refresh token is revoked         |
| POST   | `/user/logout`                 | ✔    | `204`. Optional `{refreshToken}`; without it all sessions are revoked |
| PATCH  | `/user/password`               | ✔    | `{currentPassword, newPassword}` → `204`; revokes all refresh tokens  |
| POST   | `/user/password/reset-request` | –    | `202` with the same answer whether or not the email exists            |
| POST   | `/user/password/reset`         | –    | `{resetToken, newPassword}` → `204`; single-use                       |

### Users (own account only; any other id returns `404`)

| Method | Path          | Notes                                                         |
| ------ | ------------- | ------------------------------------------------------------- |
| GET    | `/users/{id}` | Profile                                                       |
| PATCH  | `/users/{id}` | `name`, `email`, `phone`, `fcm_token` (null clears the token) |
| DELETE | `/users/{id}` | Soft delete; sessions revoked, baggage rows kept              |

### Baggage (owner only; other users' records return `404`)

| Method | Path                   | Notes                                                             |
| ------ | ---------------------- | ----------------------------------------------------------------- |
| POST   | `/baggage`             | `201`. `user_id` and `token_id` are set by the server             |
| GET    | `/baggage`             | `?page=1&limit=20&status=&category=` → `{items,page,limit,total}` |
| GET    | `/baggage/{id}`        |                                                                   |
| PATCH  | `/baggage/{id}`        | Partial update                                                    |
| PATCH  | `/baggage/{id}/status` | `{status}`                                                        |
| DELETE | `/baggage/{id}`        | `204` (hard delete)                                               |

`category`: `general | luggage | cargo | camera | other` (default `general`)  
`status`: `active | lost | recovered` (default `active`)

Both are plain strings backed by the enums in `app/core/enums.py`, stored as `VARCHAR`.
To add a value, edit the enum — no migration is needed.

### Errors

Every error uses one shape:

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "category: Input should be ...",
    "details": []
  }
}
```

`400` validation / bad input · `401` missing or invalid token · `404` missing or not yours ·
`409` duplicate (email) · `429` rate limited · `500` unexpected (no internals exposed).
Submitted values (e.g. passwords) are never echoed back in validation errors.

## Differences from `CRUD_API.md`

These follow your project changes; adjust the Flutter models accordingly.

| Contract says                                      | This API                                                |
| -------------------------------------------------- | ------------------------------------------------------- |
| integer `id` / `user_id`                           | UUID strings                                            |
| `category`, `status` as `{id, name}` (sent as ids) | plain enum strings, sent and returned as strings        |
| `GET /users` (admin list)                          | not implemented (single user role)                      |
| error body `{"error": {...}}`                      | `{"success": false, "error": {code, message, details}}` |
| collection returns a list                          | returns `{items, page, limit, total}`                   |

## Project Structure

```text
app/
├── api/              # Route handlers (thin) + dependencies
│   ├── deps.py       # DB session, CurrentUser
│   └── v1/endpoints/ # auth, users, baggage
├── core/             # config, enums, exceptions, error handlers, security, rate limit, middleware
├── database/         # engine/session (base.py), UTCDateTime type
├── models/           # User, Baggage, RefreshToken, PasswordResetToken
├── repositories/     # Data access (queries only)
├── schemas/          # Pydantic request/response models
├── services/         # Business logic; commits the transaction
└── utils/            # mixins, logger, validations, notifications hook
alembic/              # Migrations (0001 = initial schema)
tests/                # pytest suite (SQLite)
```

## Development

```bash
make test                      # or: pytest
make lint && make format
make revision MSG="describe"   # alembic autogenerate
make migrate                   # alembic upgrade head
```

The suite includes a test that applies the migrations and runs `alembic check`, so a model
change without a matching migration fails CI.

## Design Notes

- **Transactions:** services call `commit()` before returning. Do not commit in the `get_db`
  dependency: in current FastAPI the code after `yield` runs _after_ the response is sent.
- **Tokens:** access tokens are short-lived JWTs (stateless; valid until expiry). Refresh and
  reset tokens are random strings stored only as SHA-256 digests. Refresh tokens rotate on every
  use; replaying an already-rotated token revokes all of that user's sessions.
- **Passwords:** bcrypt, run in a thread pool. Passwords over 72 bytes are rejected (bcrypt
  would otherwise truncate or error).
- **Soft delete:** deleted users keep their row, so their email stays reserved.

## Known Gaps / Next Steps

- **Password-reset delivery:** `app/utils/notifications.py` is a stub. Plug in an email provider.
- **Rate limiting** is in-memory per process. Behind several replicas, enforce it in API
  Management (or Redis).
- **Request size limits** should be set at API Management / the ingress.
- Not yet covered: a public "finder scans a QR code" lookup by `token_id`.

## License

Proprietary — All rights reserved.

## CURLS

# 1. sign up (copy "accessToken" from the response)

curl -s -X POST http://127.0.0.1:8000/api/signUp \
 -H 'content-type: application/json' \
 -d '{"name":"John Doe","email":"john@example.com","password":"correct-horse-1","phone":"123-456-7890","fcm_token":"test-token"}'

# 2. create a bag (copy "token_id" from the response)

curl -s -X POST http://127.0.0.1:8000/api/baggage \
 -H "authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIzOWYwNDk4OC1mZTNmLTRlMTEtOWRkYi0zZDY1OWVjNDY2NzAiLCJ0eXBlIjoiYWNjZXNzIiwiaWF0IjoxNzkzNDU4ODgyLCJleHAiOjE3OTM0NjA2ODJ9.bHdk7aj8rr4i0BlSXByzD39tUcfbzQAoLU9eigOl_lQ" \
 -H 'content-type: application/json' \
 -d '{"name":"My Laptop Bag","category":"luggage","color":"#112233","brand":"Acme"}'
OC1mZTNmLTRlMTEtOWRkYi0zZDY1OWVjNDY2NzAiLCJ0eXBlIjoiYWNjZXNzIiwiaWF0IjoxNzkzNDU4ODgyLCJleHAiOjE3OTM0NjA2ODJ9.bHdk7aj8rr4i0BlSXByzD39tUcfbzQAoLU9eigOl_lQ" \
  -H 'content-type: application/json' \
  -d '{"name":"My Laptop Bag","category":"luggage","color":"#112233","brand":"Acme"}'
