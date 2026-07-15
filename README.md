# AIOps Agent (prototype)

Natural-language agent for Google Cloud infrastructure: list/inspect Compute
Engine VMs, GKE clusters, and Cloud SQL instances; pull CPU metrics; summarize
recent alerts; restart a VM — all via a chat UI, using **the visitor's own
GCP credentials** (Google OAuth), not a shared service account.

This is a working product prototype. Full architecture/design docs, demo
video, and hosted-deployment notes come next — this README is just enough to
run it locally.

## Quick start

1. `cd backend && pip install -r requirements.txt`
2. Copy `.env.example` to `.env` (project root) and fill in:
   - `GEMINI_API_KEY` — from [Google AI Studio](https://aistudio.google.com/apikey)
   - `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` — create an OAuth 2.0 Web
     Client in Google Cloud Console → APIs & Services → Credentials, with
     authorized redirect URI `http://localhost:8000/auth/callback`.
   - `SESSION_SECRET` — any long random string.
3. From `backend/`: `uvicorn main:app --reload --port 8000`
4. Open `http://localhost:8000`, sign in with Google, pick a project, chat.

The signed-in Google account needs the relevant IAM roles on the target
project (e.g. Compute Viewer/Instance Admin, Kubernetes Engine Viewer, Cloud
SQL Viewer, Monitoring Viewer, Logs Viewer) for the corresponding tools to
return data instead of permission errors.

## Docker

```
docker build -t aiops-agent .
docker run -p 8080:8080 --env-file .env aiops-agent
```

## Known scope cuts (prototype stage)

- Sessions are in-memory (single process, not persisted across restarts).
- OAuth scope is broad (`cloud-platform`) for simplicity.
- "Alerts" are derived from Cloud Logging severity, not a full Monitoring
  alerting-policy integration.

Full documentation covering architecture, setup, design decisions,
assumptions, and limitations will be added separately.
