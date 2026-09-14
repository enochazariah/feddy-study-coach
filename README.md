# Feddy (AI Study Coach)

**Hackathon track:** AWS Agents for Humans Hackathon

Feddy is an AI-powered study coach that helps learners understand difficult concepts,
ask better questions, and keep momentum during independent study.

## Architecture

```text
React + Vite + Tailwind CSS frontend
              | JSON over CORS
Django + Django REST Framework backend
              | boto3 Bedrock Runtime
Amazon Bedrock (Anthropic Claude 3 Haiku)
```

The backend owns the model call and keeps AWS credentials server-side. The frontend
provides the study workflow and communicates with Django through the typed API client.

## Key features

- Intelligent tutoring chat with Feddy.
- Document and study assistance foundation for focused learning workflows.
- Responsive chat experience with loading and connection-error states.
- Full-stack communication between the Vite client, Django API, and Amazon Bedrock.
- CORS configuration for local frontend development.

## Run locally

### Prerequisites

- Python 3.10 or newer
- Node.js 18 or newer
- An AWS account with access to the configured Amazon Bedrock model

### 1. Configure and run Django

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `backend/.env` with AWS credentials, `AWS_REGION`, `DEBUG`, and an enabled
`BEDROCK_MODEL_ID`. Never commit this file or place credentials in the frontend.

```powershell
python manage.py migrate
python manage.py runserver
```

The API runs at `http://localhost:8000`.

### 2. Run the React frontend

In a second terminal:

```powershell
cd web
npm install
copy .env.example .env
npm run dev
```

The frontend runs at `http://localhost:5173` and uses Django at
`http://localhost:8000/api` by default.

## Validation

```powershell
cd backend
python manage.py check

cd ..\web
npm run build
```

The repository includes focused backend tests under `backend/accounts/tests` and
`backend/tutoring/tests`.

## Security

Use least-privilege AWS credentials with only the Bedrock permissions required by the
application. Rotate any credential that has been shared outside a secure secret store.
The root and backend ignore rules exclude `.env` files and `node_modules`.
