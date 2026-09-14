# Feddy Study Coach — Technical Handoff Report

> **Superseded note:** this report describes the `openai-agents` (OpenAI Agents SDK)
> build. The Tutor Agent was later rewritten on the **Strands Agents SDK**
> (`strands-agents[openai]`) — same behavior, same Phase 1 scope, different package.
> Every verification claim below (auth, DB, tests, CORS, rate limiting) still holds; only
> §6 (OpenAI Agents SDK specifics) is package-specific and now describes the prior SDK.
> See the conversation history for the Strands rewrite details, or `tutoring/tutor_agent.py`
> for the current implementation.

Everything below is scoped strictly to what exists in code and what was actually run in
this session. Where something was written but not executed against a real service, that's
stated explicitly rather than implied.

---

## 1. Project Structure

Two separate, currently disconnected codebases exist on disk:

```
feddy-study-coach-django/          # the current backend — Django
└── backend/
    ├── manage.py
    ├── requirements.txt
    ├── .env.example
    ├── config/                     # settings, root urls, wsgi
    │   ├── settings.py
    │   ├── urls.py
    │   └── wsgi.py
    ├── accounts/                   # Google auth, AppUser, JWT sessions
    │   ├── models.py                # AppUser
    │   ├── google_auth.py           # verify_google_id_token
    │   ├── tokens.py                 # issue/verify_session_token (JWT)
    │   ├── authentication.py        # DRF SessionTokenAuthentication
    │   ├── services.py              # find_or_create_user
    │   ├── serializers.py
    │   ├── views.py                 # google_sign_in, me
    │   ├── urls.py / user_urls.py
    │   └── migrations/0001_initial.py
    └── tutoring/                   # subjects, conversations, the tutor agent
        ├── models.py                # Subject, Topic, LearningSession, Conversation, Message, AgentRun
        ├── tutor_agent.py           # build_tutor_agent() — OpenAI Agents SDK
        ├── services.py              # conversation persistence
        ├── views.py                 # list_subjects, list_topics, tutor_chat
        ├── urls.py
        └── migrations/0001_initial.py, 0002_seed_subjects.py

feddy-study-coach/                 # the earlier Node/Express Phase 1 build — SUPERSEDED
├── server/                         # Express + TS backend — not used going forward
└── web/                            # React + Vite frontend — REUSABLE, see §2
```

**The React frontend was built against the now-superseded Node backend and has never
been copied into, or run against, the Django project.** It shares the same REST contract
(`/api/auth/google`, `/api/user/me`, `/api/subjects`, `/api/tutor/chat`) by design, but
that's a structural claim, not a tested one — see §9.

---

## 2. Frontend

- **Framework:** React 18.3.1 + Vite 5.4.8 + TypeScript, via `react-router-dom` 6.26.2.
- **Entry point:** `web/src/main.tsx` → `App.tsx`, routes: `/` (Landing), `/dashboard`, `/tutor`.
- **State management:** local `useState`/`useEffect` only, plus one React Context
  (`AuthContext`) holding the current user and session token. No Redux/Zustand/etc.
- **API client:** `web/src/api/client.ts` — a thin `fetch` wrapper that attaches
  `Authorization: Bearer <token>` from `localStorage`.
- **Auth flow (client side):** Google Identity Services script → `GoogleSignInButton`
  renders Google's own button → on success, posts the ID token to
  `/api/auth/google` → stores the returned session token in `localStorage`.
- **Student-facing features implemented:** landing page, Google sign-in, subject/topic
  picker (Dashboard), a single-mode-at-a-time tutor chat screen (`TutorChat.tsx`) with a
  mode selector (beginner/standard/deep/socratic/practice).
- **What was actually verified:** `tsc --noEmit` passes cleanly. **The app has never been
  run in a dev server or a browser in this session.** No visual QA, no click-through, no
  confirmation the Google button actually renders or that routing works at runtime.

---

## 3. Django Backend

- **Django version installed and verified:** 5.0.14 (requirements.txt pins `>=5.0,<5.1`).
- **Installed apps:** `admin`, `auth`, `contenttypes`, `sessions`, `messages`,
  `staticfiles`, `rest_framework`, `corsheaders`, `accounts`, `tutoring`.
- **Settings structure:** single `config/settings.py`, no split dev/prod settings files —
  everything is environment-variable-driven via `python-dotenv`. `DEBUG`, `ALLOWED_HOSTS`,
  `DATABASE_URL`, `GOOGLE_CLIENT_ID`, `SESSION_JWT_SECRET` are all read from env; missing
  required vars crash startup immediately (`os.environ["..."]`, not `.get()`).
- **URL configuration:** `config/urls.py` includes `accounts.urls` at `/api/auth/`,
  `accounts.user_urls` at `/api/user/`, `tutoring.urls` at `/api/`. `APPEND_SLASH = False`
  so routes match the frontend's exact strings (no Django trailing-slash redirects).
- **REST Framework config:** default authentication class is our custom
  `SessionTokenAuthentication`; default permission class is `IsAuthenticated`. This means
  every endpoint requires a valid Bearer token **unless explicitly opted out**, which is
  what `google_sign_in` does via `@authentication_classes([])` + `@permission_classes([AllowAny])`.
- **API endpoints (code-level, see §8 for test status):**
  `POST /api/auth/google`, `GET /api/user/me`, `GET /api/subjects`,
  `GET /api/subjects/<uuid:subject_id>/topics`, `POST /api/tutor/chat`.
- **Services layer:** `accounts/services.py` (`find_or_create_user`),
  `tutoring/services.py` (conversation/message persistence, `record_agent_run`). No LLM
  calls happen in the services layer — that's isolated to `tutor_agent.py` + `views.py`.
- **Authentication implementation:** custom, described fully in §5.
- **Authorization implementation:** every DB query in `tutoring/services.py` that touches
  conversations is filtered by the `user` derived from the authenticated request, never
  from a client-supplied id — see `get_or_create_conversation`.
- **Rate limiting:** `django-ratelimit` 4.1.0, applied only to `POST /api/tutor/chat`
  (`key="user", rate="20/m", block=True`). Required adding a `.pk` alias to our custom
  auth-user wrapper for the library's `user` key to resolve correctly. **Never tested
  under actual repeated requests** — only confirmed it doesn't break `manage.py check`.

---

## 4. Database

Six models exist. All use `UUIDField` primary keys (`default=uuid.uuid4`), not
auto-incrementing integers.

| Model | Purpose | Key fields | Relationships | Owner |
|---|---|---|---|---|
| `AppUser` | The only user model — Google OAuth only, **no password field exists anywhere in the schema** | `google_sub` (unique), `email` (unique), `display_name`, `avatar_url`, `last_login_at` | none | — (this *is* the user) |
| `Subject` | Top-level subject (e.g. Machine Learning) | `slug` (unique), `name` | has many `Topic` | none — global reference data |
| `Topic` | Topic within a subject | `slug`, `name` | FK → `Subject` | none — global reference data |
| `LearningSession` | A study session with a mode | `mode` (choice field) | FK → `AppUser`, optional FK → `Subject`/`Topic` | `AppUser` |
| `Conversation` | A chat thread | — | FK → `AppUser`, optional FK → `LearningSession` | `AppUser` |
| `Message` | One turn in a conversation | `role` (user/assistant/system), `content` | FK → `Conversation` | indirectly via `Conversation.user` |
| `AgentRun` | Observability record per agent invocation | `agent_name`, `status`, `latency_ms`, `error_message` | FK → `AppUser`, optional FK → `Conversation` | `AppUser` |

**Migrations:** `accounts/migrations/0001_initial.py`, `tutoring/migrations/0001_initial.py`,
`tutoring/migrations/0002_seed_subjects.py` (data migration seeding "Machine Learning" and
"Mathematics"). All three **were actually applied**, twice, against a real SQLite database
in this session (`manage.py migrate`) — full output captured, zero errors. They have
**never been applied against Postgres** — no Postgres instance has existed in this sandbox
at any point (`DATABASE_URL` in every test was either fake or pointed at a nonexistent
local server).

---

## 5. Authentication

Flow as coded:

```
Student clicks Google button (React, Google Identity Services)
  → Google returns a signed ID token to the browser
  → React POSTs { idToken } to /api/auth/google
  → Django verifies the token DIRECTLY WITH GOOGLE
    (google.oauth2.id_token.verify_oauth2_token, checked against GOOGLE_CLIENT_ID)
  → payload.email_verified is checked; unverified emails are rejected
  → find_or_create_user() looks up AppUser by google_sub (never by email alone)
  → Django issues its own JWT (PyJWT, HS256, 7-day expiry) via issue_session_token()
  → React stores that JWT in localStorage
  → Every subsequent request sends Authorization: Bearer <jwt>
  → SessionTokenAuthentication decodes it, loads the AppUser, attaches it to request.user
```

**What was actually tested successfully:** none of this end-to-end. No real Google OAuth
client was used, no real browser flow was run, no real ID token was ever verified. What
*was* verified: the code compiles/type-checks, `AppUser.objects.get_or_create` behavior
was exercised implicitly by the migration/model checks, and the JWT encode/decode logic
was inspected but not executed with a live token.

**Confirmed: no Gmail/Google password is stored anywhere.** There is no password field on
`AppUser`, no password-handling code path anywhere in `accounts/`, and Google's own
Identity Services flow never exposes a password to this application in the first place —
structurally impossible for this app to see one.

---

## 6. OpenAI Agents SDK

- **Package name:** `openai-agents` (imports as `agents`).
- **Installed version, verified via `pip freeze`:** `openai-agents==0.22.0`, with
  `openai==3.6.0` as its underlying client dependency. Python 3.12.3 used for verification
  (SDK requires 3.10+).
- **Agent definition:** `tutoring/tutor_agent.py`, `build_tutor_agent(mode)` returns
  `Agent(name="Adaptive Tutor", instructions=..., model="gpt-4.1-mini")`. One agent, no
  tools, no handoffs.
- **Runner usage:** `Runner.run_sync(agent, conversation_input)` in `tutoring/views.py`,
  called synchronously inside a DRF view (not the async `Runner.run`).
- **Model configuration:** hardcoded `"gpt-4.1-mini"` — not env-configurable yet.
- **System instructions:** a fixed base instruction block (states the tutor's purpose is
  to build independence, not dependence) concatenated with a per-mode instruction string
  for one of beginner/standard/deep/socratic/practice.
- **Conversation history handling:** we do **not** use the SDK's Sessions feature. History
  is pulled from our own `Message` table and rebuilt as a plain list of
  `{"role": ..., "content": ...}` dicts on every call. This was specifically checked
  against the SDK's actual `EasyInputMessageParam` type (installed package inspected
  directly) — plain string content is valid for this SDK, unlike the TypeScript SDK where
  the same pattern originally failed type-checking and had to be restructured.
- **AgentRun persistence:** every call to `tutor_chat` writes exactly one `AgentRun` row,
  success or failure, with latency in milliseconds.
- **Error handling:** a broad `except Exception` around the `Runner.run_sync` call —
  logs the error to `AgentRun.error_message`, returns HTTP 502 with a generic message.
  Never fabricates a reply on failure.

**Confirm that the Tutor Agent has actually executed successfully: No.** There is no
`OPENAI_API_KEY` with real credit behind it in this sandbox, and `api.openai.com` is not
reachable from this environment's network sandbox at all (only pypi.org, github.com, and
a handful of package registries are allowlisted). Everything above was verified
structurally — the code imports correctly, the types match the SDK's real definitions,
`Agent()` and `Runner` construct without error — but **no live call to OpenAI has ever
been made from this code.** Your real API key changes this the moment you run it locally.

---

## 7. Current Agent Capabilities

**Implemented and tested (structurally, via `manage.py check`/migrations/type-checking):**
- Single Tutor Agent construction with mode-based instructions
- Conversation history persistence and reconstruction into SDK-compatible input
- AgentRun logging on both success and failure paths

**Implemented but not fully tested (no live execution against OpenAI or in a browser):**
- Actual agent responses (never received one)
- The full request lifecycle from React through Django to the agent (never run)
- Rate limiting behavior under real repeated load
- Google OAuth end-to-end

**Planned only (no code exists at all):**
- Any handoffs or agents-as-tools
- Research Agent, Assessment Agent, ML/Data Agent
- Hosted web search / file search / code interpreter / hosted MCP
- Learner Model, mastery scoring, Knowledge Graph
- Practice engine, Assessment engine, misconception detection
- Teacher/Admin roles of any kind

---

## 8. API Testing

| Endpoint | Code exists | Tested |
|---|---|---|
| `POST /api/auth/google` | Yes | **No** — never called, real or fake |
| `GET /api/user/me` | Yes | **No** |
| `GET /api/subjects` | Yes | **No** |
| `GET /api/subjects/<id>/topics` | Yes | **No** |
| `POST /api/tutor/chat` | Yes | **No** |

No HTTP requests — real or synthetic — have been made against any endpoint in this
session. `manage.py check` and `manage.py migrate` verify the app *starts* and the schema
*applies*; neither exercises a single view function. There is currently no test client
usage, no `curl`/httpie session, nothing. This is the single biggest gap between "code
exists" and "code works" in this handoff.

---

## 9. Frontend → Backend → Agent

**This full path has never been demonstrated, in any form, real or mocked.** No Django
dev server has been started in this session; no Vite dev server has been started; no
request has crossed from React to Django, let alone from Django to OpenAI. The claim that
they're compatible rests entirely on the REST contract being written to match on both
sides (same paths, same JSON field names) — that's a design claim, not a verified one.

---

## 10. Security

| Area | Status |
|---|---|
| Secrets management | `.env.example` templates only; `os.environ[...]` (not `.get()`) for `DJANGO_SECRET_KEY`, `SESSION_JWT_SECRET`, `GOOGLE_CLIENT_ID`, `DATABASE_URL` — missing values crash startup rather than silently degrading |
| OpenAI API-key handling | **Gap:** never explicitly validated in `settings.py` the way the others are — the `openai-agents` SDK picks `OPENAI_API_KEY` up implicitly from the environment, so a missing key fails at *call time*, not startup |
| Google token verification | Done server-side against Google directly; `email_verified` checked; never trusts client-asserted identity — but never run against a real token |
| JWT handling | HS256, 7-day expiry, dedicated `SESSION_JWT_SECRET` distinct from `DJANGO_SECRET_KEY` |
| User data isolation | Enforced in the services layer via `user`-scoped queries, not in views or serializers — reviewed by reading, not tested with a second user account |
| Rate limiting | Present on `/api/tutor/chat` only; not on auth or subject endpoints |
| CORS | `django-cors-headers` installed, `CORS_ALLOWED_ORIGINS` from env; never exercised by an actual cross-origin browser request |
| CSRF | Django's `CsrfViewMiddleware` is active (default middleware stack) but irrelevant to our Bearer-token API endpoints, since they don't use `SessionAuthentication`/cookies — it still protects `/admin/` if you use it |
| Input validation | Manual (`len(message) > 4000`, mode whitelist) in `tutor_chat`; no schema library (no DRF serializer validation on that endpoint specifically) |
| Agent/tool permissions | Not yet applicable — zero tools are wired to the agent |

**Needs hardening before any real traffic:** explicit `OPENAI_API_KEY` presence check at
startup, DRF serializer-based validation on `tutor_chat` instead of manual checks, and
actual verification of the CORS/rate-limit behavior against a running server.

---

## 11. Tests

**None exist.** No `tests.py`, no `pytest` files, no `tests/` directories anywhere in
either codebase — confirmed by an exhaustive filesystem search
(`find ... -iname "*test*"` returned zero application test files). No unit tests, no
integration tests, no authentication tests, no API tests, no agent tests. The only
"testing" performed in this whole build has been: TypeScript compilation, Django's
`check` and `makemigrations`/`migrate` commands, and manual inspection of installed SDK
type definitions. None of that is a substitute for actual test coverage.

---

## 12. Deployment

**Nothing is deployed.** This entire project — Django backend and React frontend alike —
exists only as local files, generated and verified in this sandboxed environment. There
is no live frontend hosting, no live backend hosting, no live database, and no production
configuration of any kind. (Separately, your project history mentions a previously
deployed Django + React "Feddy Study Coach" on Netlify + Render + Supabase — but that is
not the codebase in this handoff, and I have not inspected it directly.)

**Local development, as designed but not yet run:** Postgres via `DATABASE_URL`
(Supabase-compatible), `manage.py runserver` for the API, `npm run dev` (Vite) for the
frontend, `.env` files on both sides populated from the `.env.example` templates.

---

## 13. Architectural Limitations

The system, as it exists right now, **cannot**:

- Access any file the student uploads (no File Search, no upload endpoint, no storage)
- Search the web (no hosted Web Search tool wired in)
- Execute or analyze code/data (no Code Interpreter, no ML/Data tooling)
- Delegate to a specialist agent of any kind (no handoffs, no agents-as-tools — the
  orchestrator/Research/Assessment/ML-Data diagram you sent is 100% unbuilt)
- Track what a student actually understands (no Learner Model, no mastery evidence)
- Represent concept relationships or prerequisites (no Knowledge Graph)
- Generate or grade an assessment, or run a practice loop with adaptive difficulty
- Detect a misconception
- Do anything for a teacher or admin account — those roles don't exist in the schema
- Support any research workflow beyond a single agent's own general knowledge

---

## 14. Next Architectural Step

The smallest safe increment is **not** a new agent, a new framework, or a rewrite — it's
proving the thing that exists actually works, end to end, with your real credentials:

1. Stand up a real Postgres database (local or Supabase) and point `DATABASE_URL` at it;
   run `manage.py migrate` for real.
2. Create a real Google OAuth 2.0 Web client, add `http://localhost:5173` as an
   authorized origin, put the client ID in both `.env` files.
3. Put your real `OPENAI_API_KEY` in `backend/.env`.
4. Copy the `web/` frontend into the Django project (or keep it alongside — path doesn't
   matter, correctness does) and run both dev servers.
5. Do one real thing: sign in with your actual Google account, send one real message to
   the tutor, and confirm a real OpenAI-generated reply comes back and is persisted in
   `Message`/`AgentRun`.

Only once that succeeds for real does it make sense to talk about Research/Assessment/
ML-Data agents, the Learner Model, or the Knowledge Graph — building orchestration on top
of an unverified foundation would mean debugging two unknowns at once instead of one.
