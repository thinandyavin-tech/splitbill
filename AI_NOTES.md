# AI notes

## Tools used

- **Claude Code (Claude Opus 5.5)**, an agentic coding assistant in the terminal. It wrote nearly
  all of the code, tests, migrations and these docs from the brief PDF. It also ran the linters,
  type-checker, build and tests itself, and made the commits.
- Guidance used alongside it: the "Karpathy guidelines" skill (keep changes minimal, no
  speculative abstractions, define verifiable success criteria before coding).

## Effective prompts

1. The starting prompt was the brief itself: *"can you do all this for me"* plus the PDF. This
   worked because the brief is very concrete (exact numbers, error cases, required tests). The
   assistant turned each business rule and each required test into a pass/fail check before
   writing code.
2. Asking it to **write the pure money module and its unit tests first**, before any database
   code. Satang allocation and parsing were then pinned down independently of FastAPI and Postgres,
   and the frontend mirrored the same function and test cases.

## Incorrect or unsafe AI output, and how it was caught

All of these happened while building this repository.

1. **Amount regex accepted input it shouldn't (unsafe).** The first `money.py` used
   `re.match(r"^\d{1,10}(\.\d{1,2})?$", value)`. Two problems:
   - In Python, `$` also matches *before a trailing newline*, so `"100.00\n"` passed validation.
   - `\d` matches any Unicode digit, so Thai numerals like `"๑๐๐"` passed, and `Decimal()` would
     happily parse them.

   It also limited the input to 10 integer digits, which made the "too large" check below it
   unreachable dead code. **Detection:** a line-by-line re-read of the money module, asking "what
   strings does this regex accept that it shouldn't?" **Fix:** `re.fullmatch` with `re.ASCII`,
   drop the digit cap so the explicit size check is the single rule, and add regression tests for
   `"100.00\n"`, `"๑๐๐"`, `".50"` and `"5."`.

2. **Zero balance rendered as `"0"` instead of `"0.00"`.** The first balance code did
   `str(paid.get(id, 0) - owed.get(id, 0))`. A member with no expenses got `int 0 - int 0`, and
   the string was `"0"`, which broke the documented `"0.00"` format. **Detection:** reviewing the
   types flowing through the expression. **Fix:** convert database `Decimal`s to integer satang
   and format everything through one function, `format_amount`.

3. **Reference to a function that didn't exist.** The first `expense_out()` called an undefined
   `_username(...)` helper to get the creator's name. **Detection:** reading the generated
   service file before running it. **Fix:** add a `created_by` relationship on the model and
   load it with the other relationships.

4. **Seed migration that failed in offline mode.** `sa.table("users", sa.column("id"), ...)` had
   untyped columns, so `alembic upgrade head --sql` crashed with "No literal value renderer is
   available". **Detection:** rendering the migrations to SQL before any database was available.
   **Fix:** give the lightweight table columns explicit types.

5. **A concurrency test that didn't test concurrency.** The first idempotency race test fired
   8 threads through FastAPI's `TestClient` with a barrier and asserted one `201` and seven `200`s.
   It passed, but the requests were effectively serialized, so the `ON CONFLICT` path never ran.
   **Detection:** mutation testing. Each business rule was broken on purpose in a throwaway clone,
   and the suite was checked for a failure. Deleting `ON CONFLICT DO NOTHING` entirely left every
   test green. **Fix:** a deterministic test. Session A inserts the key without committing, request
   B runs in a thread, the test asserts B is blocked, and after A commits it asserts B returns A's
   expense. The mutation is now caught, as are the other 7 (leftover satang order, group access,
   payer-only delete, exact-sum check, 3-decimal rejection, soft-delete exclusion, split
   membership).

6. Smaller ones caught by tooling: a stray closing parenthesis in the React form (caught by
   ESLint and `tsc`), and import-order churn because ruff took the local `alembic/` folder for
   first-party code (fixed with `known-third-party`).

## Review process before each commit

The assistant ran this loop before each commit, and the commit history follows these steps:

1. Re-read the diff against the brief's rule it implements.
2. Backend: `uv run ruff check . && uv run ruff format --check .` and `uv run pytest`.
3. Frontend: `npm run lint`, `npx tsc --noEmit`, `npm test`, `npm run build`.
4. Commit only when all of the above pass, with one logical step per commit.

One honest exception: no PostgreSQL was available while the API tests were written, so they were
committed after only lint checks. They were first run once Postgres was installed, and all 40
backend tests passed. After that, the app was checked by hand in a browser: the brief's dinner
example, the live 33.34/33.33/33.33 preview, the 0.1 + 0.2 = 0.30 exact split with submit
disabled until the shares add up, and balances updating after a save.

Before submitting, two more checks ran:

- **Mutation testing** (see item 5 above): 8 business rules were broken one at a time in a
  throwaway clone, and the suite now fails for every one.
- **An independent AI review against the brief.** A second agent was given only the PDF and the
  repository, not the first agent's reasoning, and asked to grade it strictly. It found real issues
  that were then fixed in their own commits:
  - switching user in the UI briefly showed a false "not a member" error
  - `GET /groups/99999999999` returned a plain-text 500, breaking the "consistent JSON errors"
    standard
  - one route called the repository directly
  - the README claimed Node 20 (the tests need 22.18+) and had a wrong `cd` in the test
    instructions

  It also pointed out that the regex fix in item 1 landed inside the "Add expense, group and
  balance endpoints" commit instead of its own commit. That is accurate: the history isn't
  perfectly one-step-per-commit there.

<!-- TODO(author): describe your own review of the AI-generated code here before submitting. -->
