# Feddy Study Coach

Feddy helps learners study documents, explore concepts, practise questions,
and revisit mistakes through an AI-assisted learning workflow.

## Features

- Tutor Chat: explanations, worked examples, and understanding checks.
- PDF Hub: document extraction, batched analysis, topic lessons, feedback,
  and saved document concept state.
- Active Recall: multiple-choice and theory questions, grading, feedback,
  and set review.
- Quiz-to-tutor context: authenticated users can ask the tutor about recent
  saved quiz results, including after a page refresh.
- Research and Video: Tavily reading search and embedded YouTube videos.
- Google Sign-In with backend token verification.

## Architecture

The React + Vite frontend communicates with Django REST Framework.
Backend agents use the Strands Agents SDK with Amazon Bedrock.
The backend also manages authentication, document processing, and SQLite
persistence for local development.

External services include Google Sign-In, Tavily, and YouTube Data API v3.
AWS credentials and search API keys remain on the backend.

See [architecture documentation](docs/ARCHITECTURE.md).
The model and region are configured through BEDROCK_MODEL_ID and AWS_REGION;
they are not selected in the browser.

## Local setup: Windows PowerShell

### Prerequisites

- Python 3.13: backend tests were verified using Python 3.13.7.
- Node.js 20.x or 22 and newer, with npm, for the Vite 6 / React Router 7 frontend. Locally tested with Node.js 24.19.0.
- Git.
- Authorized access to the configured Amazon Bedrock model.
- A Google OAuth web client.
- Tavily and YouTube API credentials for their respective search features.

Other Python versions and platforms have not been verified by this setup guide.
External service usage may incur charges.

### 1. Clone and install backend dependencies

Run in the parent directory where you want the project:

```powershell
git clone https://github.com/enochazariah/feddy-study-coach.git
Set-Location .\feddy-study-coach
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
Copy-Item .\backend\.env.example .\backend\.env
```

The copy command is for a fresh checkout. Do not overwrite an existing
configured .env file.

### 2. Configure local environment files

Edit backend/.env locally:

| Variable | Purpose |
| --- | --- |
| SECRET_KEY | Unique Django secret |
| SESSION_JWT_SECRET | Separate unique session-signing secret |
| DEBUG | True for local development only |
| ALLOWED_HOSTS | Local backend hosts |
| CORS_ALLOWED_ORIGINS | Exact frontend origins, including port 5173 |
| DATABASE_URL | Optional database URL; leave unset for the verified local SQLite fallback |
| AWS_ACCESS_KEY_ID | Authorized AWS credential |
| AWS_SECRET_ACCESS_KEY | Corresponding AWS secret |
| AWS_REGION | Region with access to the selected model |
| BEDROCK_MODEL_ID | Accessible Bedrock model or inference profile ID |
| GOOGLE_CLIENT_ID | Google OAuth web client ID |
| TAVILY_API_KEY | Reading search credential |
| YOUTUBE_API_KEY | YouTube Data API credential |
| ALLOW_DEMO_LOGIN | Leave False for the documented Google login flow |

For temporary AWS credentials, include AWS_SESSION_TOKEN as required by
your credential provider.

Generate each signing secret separately:

```powershell
& .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Store generated values only in your local configuration. Do not publish them.

Create the frontend environment file:

```powershell
Copy-Item .\web\.env.example .\web\.env
```

Set `VITE_API_URL=http://localhost:8000/api`. The client appends request paths such
as `/accounts/me` to this base URL, so the `/api` suffix is required. Set
`VITE_GOOGLE_CLIENT_ID` to the same OAuth client ID as `GOOGLE_CLIENT_ID`.

For local SQLite, leave `DATABASE_URL` unset while `DEBUG=True`. The backend then
uses `backend/data/feddy_study.db`. Although `settings.py` accepts SQLite URLs,
the example `sqlite:///db.sqlite3` resolves to `/db.sqlite3` on Windows, outside
the project data directory.

Configure the OAuth web client's authorized JavaScript origin to match the
frontend URL, normally http://localhost:5173. Use the same hostname consistently.
Meet any consent-screen or test-user restrictions on your Google project.

### 3. Start the backend

From the repository root:

```powershell
& .\.venv\Scripts\python.exe .\backend\manage.py migrate
& .\.venv\Scripts\python.exe .\backend\manage.py runserver
```

Keep this terminal running. The local backend is available on port 8000.

### 4. Start the frontend

Open a second terminal at the repository root:

```powershell
Set-Location .\web
npm ci
npm run dev -- --port 5173 --strictPort
```

Open http://localhost:5173 and sign in with Google.
Keep both server terminals running.

## Verification

From the repository root:

```powershell
& .\.venv\Scripts\python.exe -m pip check
& .\.venv\Scripts\python.exe .\backend\manage.py check
& .\.venv\Scripts\python.exe .\backend\manage.py test accounts.tests tutoring.tests
```

Build the frontend:

```powershell
Push-Location .\web
npm run build
Pop-Location
```

The labeled backend suite passed 78 tests in both the working environment
and a separate temporary environment installed from the corrected requirements.
Expected exception logs occur in failure-path tests; use the final test summary
to determine success.

These results do not establish a complete fresh-checkout installation,
production deployment, or live model reliability.

## Persistence and limitations

- PDF concept feedback and graded quiz evidence are stored server-side.
- Quiz evidence retrieval is user-scoped, request-triggered, and bounded
  to at most three records.
- Active Recall does not restore its visible question set after refresh.
- Tutor Chat does not restore its visible conversation history after refresh.
- Scanned-document/OCR support has not been verified.
- AI explanations and grading can be wrong; scores describe an answer or set,
  not complete mastery.
- The supplied server commands are for local development, not production hosting.

## Troubleshooting

- Connection failure: check that both backend and frontend servers are running.
- Google token timing error: synchronize the computer clock and retry login.
- CORS failure: check the exact frontend origin in CORS_ALLOWED_ORIGINS.
- Bedrock failure: check model access, region, credentials, and backend logs.
- Grading unavailable: preserve the answer and retry after resolving the cause.
- Zero tests discovered: use the explicitly labeled test command above.

## Security

Never commit real .env files, AWS credentials, API keys, signing secrets,
local databases, or private uploaded documents.

Use least-privilege AWS access. Before any public deployment, review production
configuration, HTTPS, database and file storage, authentication access, quotas,
and operational monitoring.