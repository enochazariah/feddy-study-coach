# Feddy Study Coach — FINAL_VERIFICATION.md

> **Superseded note:** verified against the `openai-agents` build. The Tutor Agent was
> later rewritten on the **Strands Agents SDK**; the rewrite was re-verified (migrations,
> full test suite, a live request against the real running server) with identical results
> — real 502 on the blocked network call, real `AgentRun` error row, zero fabricated
> replies. §6/§"OpenAI Agents SDK" details below describe the prior package specifically.

This is the state of the Foundation Verification milestone at handoff. Every item below
was either actually executed in this sandbox (commands included) or explicitly marked as
not executed. Nothing here is claimed on the basis of reading code alone.

---

## VERIFIED
*(actually executed successfully, command included)*

- **Django starts clean.**
  `python manage.py check` → `System check identified no issues (0 silenced).`
- **Migrations apply from a clean SQLite database.**
  `rm db.sqlite3 && python manage.py migrate` → all `accounts`/`tutoring`/Django-core
  migrations applied, including the `0002_seed_subjects` data migration.
- **Seed data actually exists post-migration.**
  Verified via `manage.py shell`: `Subject.objects.all()` returns "Machine Learning" and
  "Mathematics" with real UUID primary keys.
- **Django dev server actually starts and serves.**
  `python manage.py runserver 127.0.0.1:8000` → confirmed via `curl` returning real HTTP
  responses (not connection-refused).
- **Vite dev server actually starts and serves.**
  `npm run dev -- --port 5173` → `curl http://127.0.0.1:5173/` → `200`.
- **All 5 endpoints respond with real, correct HTTP behavior (unauthenticated/invalid paths):**
  - `GET /api/subjects` (no token) → `403 {"detail":"Authentication credentials were not provided."}`
  - `GET /api/user/me` (no token) → `403`, same detail
  - `POST /api/tutor/chat` (no token) → `403`, same detail
  - `POST /api/auth/google` (invalid idToken) → `401 {"error":"Google authentication failed"}`
  - `POST /api/auth/google` (missing idToken) → `400 {"error":"idToken is required"}`
- **Authenticated endpoints work correctly using a manually-issued real session JWT**
  (an `AppUser` created directly and a real token from `issue_session_token()` — Google's
  own handshake is a separate, NOT-verified item below):
  - `GET /api/user/me` → `200`, correct user JSON
  - `GET /api/subjects` → `200`, correct seeded subjects
  - `GET /api/subjects/<id>/topics` → `200`, `{"topics": []}` (correct — none seeded)
  - `GET /api/user/me` with a garbage token → `403 {"detail":"Invalid or expired session"}`
- **`POST /api/tutor/chat` correctly fails without fabricating a response.**
  Real call through the real `openai-agents` `Runner.run_sync` against the real (blocked)
  network → `502`, and the DB shows exactly what should happen: a `Conversation` row was
  created, **zero** `Message` rows were written (persistence only happens after a genuine
  success), and one `AgentRun` row with `status="error"` and the real underlying error
  text (`Host not in allowlist: api.openai.com...`).
- **Rate limiting actually blocks after 20 requests/minute**, confirmed twice: once via
  Django's `Client` test harness and once via real HTTP `curl` against the real running
  server — requests 1–20 reach the view (`502`, real OpenAI failure), request 21 onward
  is blocked (`403 {"detail":"You do not have permission to perform this action."}`).
  *(One earlier real-HTTP attempt showed no blocking at all across 22 requests — almost
  certainly a leftover server process from a prior test call still bound to the port. A
  clean re-run with a fresh process confirmed correct behavior. Flagging this rather than
  omitting it.)*
- **CORS actually works for the real React origin.**
  Preflight `OPTIONS` and a real cross-origin `GET` from `Origin: http://localhost:5173`
  against the Django server both returned `access-control-allow-origin: http://localhost:5173`.
- **14 automated tests, run for real, all pass** (`python manage.py test accounts tutoring -v 2`
  → `Ran 14 tests in 1.101s / OK`). Covers: JWT issue/verify round-trip and garbage-token
  rejection, unauthenticated access to all three protected endpoints, authenticated `/me`,
  input validation (empty/oversized message, invalid mode), conversation ownership
  isolation (a second user cannot reuse another user's conversation id), the real
  network-failure path (502, zero fabricated messages, correct `AgentRun` error), a
  **mocked** success path proving our own persistence/ownership code is correct
  independent of OpenAI, and rate limiting (21st request blocked).
- **`api.openai.com` is unreachable from this sandbox, confirmed directly:**
  `curl https://api.openai.com/v1/models` → `403`, header `x-deny-reason: host_not_allowed`.

## PARTIALLY VERIFIED
*(exercised structurally or locally, not end-to-end)*

- **The Tutor Agent construction and SDK integration** — `Agent(...)` builds correctly,
  `Runner.run_sync` is genuinely invoked with genuinely-shaped input (verified against the
  installed `openai-agents==0.22.0` package's real `EasyInputMessageParam` type) — but the
  call itself always fails at the network layer here, so **no real model response has ever
  been produced or seen**, mocked or otherwise, except in the one test that explicitly
  mocks `Runner.run_sync` to prove the surrounding code (not the model) works.
- **JWT-based authorization** — fully exercised with manually-issued tokens and confirmed
  correct end-to-end (issue → verify → DRF authenticate → user-scoped queries) — but this
  bypasses Google's actual OAuth handshake, which was not tested at all (see below).
- **Rate limiting** — confirmed correct on retest, but only under sequential single-threaded
  local requests; not tested under real concurrent load.

## NOT VERIFIED
*(requires your local environment)*

- **Google Sign-In, real browser flow.** No browser exists in this sandbox and no real
  Google OAuth Client ID was configured. The Google ID token verification code
  (`google_auth.py`) has never received a real Google-issued token.
- **Real OpenAI model responses.** Blocked entirely by sandbox network policy — see BLOCKED.
- **React UI in an actual browser.** Vite serves the built app and responds to `curl`, but
  no click-through, no visual QA, no confirmation the Google Sign-In button renders or
  that the chat UI updates correctly on a real response.
- **The full React → Django → Agent → OpenAI → React round trip.** Cannot be demonstrated
  until both Google OAuth and OpenAI access are real, which requires your machine.
- **Postgres/Supabase.** Everything above ran against SQLite, per the explicit instruction
  for this verification phase. Postgres-specific behavior (connection pooling, SSL mode,
  etc.) is unverified.

## BLOCKED

**`api.openai.com` → `403 host_not_allowed`.**

Confirmed directly with `curl -v https://api.openai.com/v1/models`, which returned the
egress proxy's own header `x-deny-reason: host_not_allowed`. This is a **sandbox network
egress restriction** in this development environment — the allowlist only includes
package registries (PyPI, npm, GitHub, etc.), not `api.openai.com`. This is **not
evidence that your API key, billing, or the Tutor Agent implementation are invalid.**
The `openai-agents` SDK, the `Agent` object, and the `Runner` call all construct and
execute correctly up to the point of the actual outbound HTTPS request — that request is
what the sandbox refuses to make. Your local machine has no such restriction.

---

## What this means practically

Everything on the Django/DRF/database/auth-token/business-logic side of this application
has real, repeatable proof behind it — commands, real HTTP responses, real DB rows, a real
passing test suite. The only genuinely unverified pieces are the two things this sandbox
structurally cannot do: complete a real Google OAuth browser handshake, and reach OpenAI's
API. Both require your local Windows/VS Code environment, which is exactly why this is the
handoff point.
