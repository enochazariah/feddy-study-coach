# Feddy Study Coach — Architecture Report (Phase 1)

> **Note:** this document was written during the initial Node/Express prototype, before
> the project standardized on Django (matching the real, already-deployed Feddy Study
> Coach). The target-architecture vision, phasing, and gap-analysis discipline below
> still apply — just mentally substitute "Django + DRF" for "Express" and
> "`openai-agents` (Python)" for "`@openai/agents` (TypeScript)" throughout. For the
> Django-specific, actually-verified state of the project, see `HANDOFF_REPORT.md` and
> `FINAL_VERIFICATION.md` in this same folder — those supersede this doc's §1–2.

## 1. Current Architecture

There is no existing working codebase for this rebuild — confirmed directly. This is a fresh build, not a migration. So the "inspect first" step in the master spec resolves to: **nothing to preserve, nothing to break.**

## 2. Target Architecture (Phase 1 scope only)

Phase 1 = Foundation, per the master spec's own phasing rule (do not build Phase 2–6 before Phase 1 is stable):

1. Project architecture (this scaffold)
2. Google authentication
3. User model
4. Database
5. Basic tutor (single agent, no handoffs yet)
6. Secure API layer
7. Basic dashboard

Everything else in the 40-part spec (Research Agent, ML/Data Agent, knowledge graph, misconception detection, teacher accounts, hosted MCP, evaluation pipelines, etc.) is **deliberately deferred**. Building them now, with zero validated foundation underneath, is exactly the "uncontrolled operation" the spec tells us to avoid.

### Why OpenAI Agents SDK is wired in now, even in Phase 1

You chose the OpenAI Agents SDK (`@openai/agents`, TypeScript) for orchestration. Verified against current docs (openai.github.io/openai-agents-js, developers.openai.com/api/docs/guides/agents):

- **Agents** — LLM + instructions + tools. Stable.
- **Handoffs** and **agents-as-tools** — for Phase 3 multi-agent delegation (Tutor → Research → ML/Data → Assessment). Stable.
- **Hosted tools** — WebSearch, FileSearch are available in the TS SDK. **Code Interpreter / sandbox is currently Python-SDK-first** — the TS SDK's sandboxing story is less mature. This matters for Part XIV (ML/Data Agent) later: we will likely run dataset/ML workflows through our own controlled backend tool rather than a hosted code-exec tool, and document that as an explicit integration boundary rather than fabricate a capability.
- **Guardrails** — input/output validation, run in parallel with the agent loop.
- **Sessions** — persistent conversation memory across `run()` calls; we still keep our own Postgres tables for mastery/learning state because Sessions ≠ Learner Model (Part XXII draws this distinction explicitly and we're keeping it).
- **Tracing** — built-in; we'll pipe this into our own `AgentRun`/`ToolCall` tables (Part XXVI) rather than only relying on OpenAI's dashboard, so observability isn't locked to one provider's UI.

So: Phase 1 ships a **single Tutor Agent, no handoffs**, built directly on the SDK's `Agent` primitive. This means Phase 3 (multi-agent) is additive later — new specialist Agents plus a `handoffs: []` array — not a rewrite.

## 3. Gap Analysis

| Capability | Status after Phase 1 |
|---|---|
| Google Sign-In | ✅ implemented |
| User isolation (server-side) | ✅ implemented (JWT + row ownership checks) |
| Database | ✅ minimal schema, extensible |
| Tutor Agent | ✅ single agent, teaching-mode aware, no handoffs |
| Explain Differently engine | ❌ Phase 4 |
| Learner Model / mastery evidence | ❌ Phase 2 (table stubbed, not scored yet) |
| Knowledge graph | ❌ Phase 2 |
| Practice / Assessment engines | ❌ Phase 2 |
| Research / ML-Data / Teacher agents + handoffs | ❌ Phase 3 |
| Misconception detection, Research Critic | ❌ Phase 4 |
| Hosted MCP, tool search/deferred loading | ❌ Phase 5 (explicit integration boundary, see §7) |
| Guardrails | ⚠️ one basic input guardrail wired as a template; expand in Phase 3+ |
| Tracing/eval pipeline | ⚠️ AgentRun table exists, not yet populated from SDK trace events |

## 4. Migration Strategy

None needed for code (fresh build). Migration strategy *does* apply going forward: each later phase should add tables/agents/tools without touching Phase 1's auth or data-isolation logic, per Rule 2 ("do not destroy working functionality").

## 5. Folder Structure

```
feddy-study-coach/
├── server/                  # Node + Express + TypeScript
│   ├── src/
│   │   ├── config/env.ts    # env var loading + validation
│   │   ├── db/               # schema.sql + pg client
│   │   ├── auth/              # Google ID token verification, JWT issuance, middleware
│   │   ├── agents/            # OpenAI Agents SDK definitions (tutorAgent.ts)
│   │   ├── routes/            # auth, user, subjects, tutor
│   │   ├── services/          # DB access, no LLM calls here
│   │   └── middleware/        # errorHandler, rateLimiter
│   └── .env.example
└── web/                     # React + Vite + TypeScript
    └── src/
        ├── auth/              # Google Sign-In button, AuthContext
        ├── pages/             # Landing, Dashboard, TutorChat
        ├── components/        # SubjectPicker, ModeSelector
        └── api/client.ts
```

## 6. Database Schema (Phase 1 subset of Part XXI)

`users`, `subjects`, `topics`, `learning_sessions`, `conversations`, `messages`, `agent_runs`.
Deliberately **not yet** creating `mastery_records`, `knowledge_graph_*`, `assessments`, `datasets`, `ml_experiments` — those are Phase 2/3 tables. Adding them now, unused, would violate Rule 3 (don't build ahead of what's real).

## 7. Managed-Agent Integration Boundary (explicit, per Rule 17)

To use this system for real, you must configure — **none of this is fabricated or assumed working out of the box**:

- `OPENAI_API_KEY` (server-side only, never sent to the browser)
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` for OAuth
- A Postgres instance (Supabase works, matching your existing stack) + `DATABASE_URL`
- `JWT_SECRET` for session signing

Hosted tools (WebSearch, FileSearch) require enabling them on your OpenAI project and are **not wired into the Phase 1 Tutor Agent** — Phase 1's tutor answers from instructions + conversation context only. Wiring hosted search in is a Phase 3 (Research Agent) task, done explicitly, not silently.

## 8. Security Model (Phase 1)

- Google OAuth only; no password storage anywhere.
- Server issues its own short-lived JWT after verifying the Google ID token server-side.
- Every DB query for conversations/messages is scoped by `user_id` derived from the verified JWT — never from a client-supplied user id.
- `OPENAI_API_KEY` lives only in `server/.env`, read by `config/env.ts`, never referenced in `web/`.
- Basic rate limiting middleware stubbed on `/api/tutor/chat`.

## 9. Testing Strategy (Phase 1)

- `services/*` are pure functions over a DB client — unit-testable with a test Postgres schema or mocked client.
- `agents/tutorAgent.ts` exports a plain `Agent` object — testable by asserting on its config (name, instructions template, model) without hitting the network; SDK-level runs are integration-tested separately.
- Auth middleware testable by mocking Google's token verification response.

---
Next step once you confirm Phase 1 works end-to-end for you: Phase 2 (Learner Model, mastery records, knowledge graph foundation, practice/assessment).
