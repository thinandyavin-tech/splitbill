# SplitBill

Shared-expense tracker: record what each member paid, split it equally or by exact amounts,
and see each member's net balance to the satang.

- `backend/`: Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16
- `frontend/`: Next.js 15, TypeScript, Tailwind CSS

## Setup

Requirements: Docker, [uv](https://docs.astral.sh/uv/), Node.js 22.18+ (the frontend tests use Node's built-in TypeScript support).

Docker Compose publishes Postgres on port 5432. If a local PostgreSQL already uses that port, stop it or change the left side of `"5432:5432"` (and `DATABASE_URL`/`TEST_DATABASE_URL` to match).

```bash
# 1. Database + API in containers (migrations and seed data run automatically)
docker compose up -d --build
# API: http://localhost:8000  (interactive docs at /docs)

# 2. Frontend
cd frontend
cp .env.example .env.local
npm install
npm run dev
# http://localhost:3000
```

The Postgres container also creates an empty `splitbill_test` database for the test suite.

### Running the API without Docker

```bash
docker compose up -d db          # or any PostgreSQL 16
cd backend
cp .env.example .env             # adjust DATABASE_URL if needed
uv sync
uv run alembic upgrade head      # schema + seed users/groups
uv run uvicorn app.main:app --reload
```

## Tests

```bash
docker compose up -d db
cd backend && cp .env.example .env   # first time only
uv run pytest                        # backend: business rules, against real PostgreSQL

cd ../frontend && npm test           # frontend money helpers (Node's built-in test runner)
```

`pytest` migrates `TEST_DATABASE_URL` to head and truncates the expense tables before each
test. It never touches `DATABASE_URL`.

Lint and format: `uv run ruff check . && uv run ruff format --check .` in `backend/`,
`npm run lint` in `frontend/`.

## API

Every request needs an `X-User` header (`alice`, `bob`, `carol` or `dan`).

| Method | Path | Notes |
|---|---|---|
| GET | `/groups` | Groups the user belongs to |
| GET | `/groups/{id}` | Group with member list |
| POST | `/groups/{id}/expenses` | `201` when created, `200` when an `Idempotency-Key` replays an earlier one |
| GET | `/groups/{id}/expenses` | Newest first; deleted expenses are left out |
| DELETE | `/groups/{id}/expenses/{expense_id}` | Payer only, soft delete, `204` |
| GET | `/groups/{id}/balances` | Positive = the member is owed money |

Errors always look like `{"error": {"code": "shares_mismatch", "message": "The shares add up to 900.00 but the amount is 1000.00"}}`.
`code` is stable and machine-readable (the frontend maps it to plain language); `message` is for humans.

| Status | When |
|---|---|
| 401 `unauthenticated` | Missing or unknown `X-User` |
| 403 `not_payer` | A member tries to delete someone else's expense |
| 404 `group_not_found` | Group doesn't exist **or** the user isn't a member |
| 404 `expense_not_found` | Expense doesn't exist in this group, or is already deleted |
| 422 `invalid_request` | Malformed request: missing field, wrong JSON type (e.g. amount sent as a number), id out of range |
| 422 `validation_error` / `shares_mismatch` / `not_group_member` / `duplicate_member` | Well-formed request that breaks a business rule |
| 500 `internal_error` | Unexpected server error (details are logged, not returned) |

## Design decisions

**Money is integer satang in the business logic.** Amounts arrive as strings and are parsed by a
strict regex (ASCII digits, at most 2 decimal places, no signs, exponents or separators) into an
`int` number of satang (`app/money.py`). All splitting and summing is integer arithmetic. At the
edges, satang become `Decimal` for the `NUMERIC(12,2)` columns and the strings in responses.
`float` is never used. The brief asks for `Decimal`, and integer satang are the same thing in
another unit. A value with exactly 2 decimal places times 100 is an exact integer, so no rounding
can ever happen. Splitting needs integer division with a remainder anyway (`divmod`), which reads
more clearly on ints than on `Decimal` with `quantize`. `Decimal` is used at every boundary: the
database columns, and parsing/formatting. JSON numbers like `10.5` are rejected (pydantic strict mode) so a float can't
sneak in through the body. `"10.005"` is rejected rather than rounded, because silently changing
someone's amount is worse than asking again.

**Leftover satang.** For an equal split, `divmod(total, n)` gives each member the base share, and
the remaining `total % n` satang go one each to the first members *in the order the client listed
them*. So 100.00 over `[alice, bob, carol]` is 33.34 / 33.33 / 33.33. Listing `[carol, bob, alice]`
gives carol the extra satang. Shares are stored per member with their position, so they always sum
to the amount exactly, and what's stored is what was shown.

**Zero-sum balances.** A balance is `sum(paid by member) - sum(member's shares)` over non-deleted
expenses. Each expense adds `amount` to the payer and `-amount` across shares that sum exactly to
`amount`, and the payer and all share members must be group members. So the group total is always
exactly 0.00. A test checks this across awkward amounts (0.01 three ways, 999.99 two ways).

**403 vs 404 for group access: 404.** For a non-member, a group they can't see is
indistinguishable from one that doesn't exist. Returning 403 would confirm that group 2 exists,
which leaks information and lets anyone enumerate group ids. Inside a group they *can* see,
the API uses 403: when bob tries to delete alice's expense he already knows it exists, so
"forbidden" is the honest and more helpful answer.

**Idempotency.** `expenses` has a unique constraint on `(group_id, idempotency_key)`. Creating an
expense:
1. looks up the key. If it exists, the original expense comes back with `200`.
2. otherwise validates, then runs `INSERT ... ON CONFLICT DO NOTHING RETURNING id`.
3. if two requests race past step 1, PostgreSQL makes the second `INSERT` wait for the first
   transaction, then it does nothing and returns no id. The code then reads and returns the
   winner's expense.

The guarantee comes from the database constraint, not from application locking, so it holds across
processes and servers. A test forces the race deterministically. Request A inserts the key and
keeps its transaction open. Request B then gets past the lookup, blocks on the `INSERT` (the test
asserts it is still waiting), and once A commits, B returns A's expense with exactly one row in the
table. The key is scoped per group, as the brief says. A replay returns the original
even if the body differs (see limitations), and even if that expense has since been deleted. It
then comes back with `"deleted": true` rather than being recreated, because the key identifies
that one expense. The header is optional; without it, or with an empty value, every POST creates
a new expense.

**Immutability and soft delete.** There is no update endpoint. Delete sets `deleted_at`. The row
and its shares stay, and every list and balance query filters on `deleted_at IS NULL`.

**Layers.** `routes.py` handles HTTP only (headers, status codes, dependencies). `service.py` holds
the business rules. `repository.py` holds the SQL. `money.py` is pure functions with no I/O.

**Frontend: no floating point.** `frontend/lib/money.ts` mirrors the backend. It parses the input
string with the same regex into an integer number of satang, splits with the same leftover-satang
rule, and formats with a manual thousands separator (`1,000.00`). So `0.1 + 0.2` is `10 + 20 = 30`
satang and displays `0.30`, and the preview always matches what the server stores. The integers
stay far below `Number.MAX_SAFE_INTEGER` (the maximum is 10¹² satang). `npm test` covers these
cases.

**Frontend idempotency.** The form generates one `Idempotency-Key` per draft and replaces it only
after a successful save. A double-click or a retry after a timeout cannot create two expenses.

## Assumptions

- **Who can add an expense:** any group member, and `paid_by` may be any member (e.g. alice
  records that bob paid). The creator is stored as `created_by`. Only the *payer* may delete, as
  the brief says.
- **The payer doesn't have to be in the split** (e.g. paying for others).
- **Exact shares** may include `"0.00"` for a member, but must not be negative and must sum to
  the amount. Equal splits can also produce 0.00 shares (0.01 split three ways).
- **A member listed twice** in an equal split is rejected (`duplicate_member`).
- **Deleting an already-deleted expense** returns 404, the same as a missing one.
- **Maximum amount** is 9,999,999,999.99, the largest value `NUMERIC(12,2)` holds.
- **Description** is required, trimmed, at most 200 characters.
- **Users list in the frontend** is hardcoded to the four seeded users. The brief has no users
  endpoint.

## Known limitations / next steps

- An idempotent replay with a *different* body returns the original expense silently. Stripe-style
  APIs store a hash of the request and return `422` on a mismatch. That would be the next step.
- `X-User` is trust-on-sight. Real authentication (sessions or JWT) would replace it.
- No pagination on the expense list.
- In the frontend, if a save times out after the server stored it and the user then *edits* the
  form and resubmits, the reused key returns the original expense. The form should regenerate the
  key whenever its content changes.
- Optional extensions not done yet: settle-up suggestions and repayments.
- No frontend component or end-to-end tests. Only the money logic is unit-tested.

## Time spent

About 1.5 hours in one AI-assisted session, plus time lost getting a local database running (see `AI_NOTES.md`). The commits are therefore close together in time, but each one is a separate logical step.
