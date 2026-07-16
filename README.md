# AIOps Agent

AIOps Agent is a prototype chat-based operations assistant for Google Cloud. It lets a user sign in with Google, connect their own GCP project, and ask plain-English questions such as:

- list Compute Engine VMs
- inspect GKE clusters
- view Cloud SQL instances
- pull CPU utilization trends
- summarize recent warning-level alerts
- restart a VM after explicit confirmation

The app uses the visitor's own Google OAuth credentials rather than a shared service account, so the backend can call Google Cloud APIs on the user's behalf.

---

## What this project does

This repository contains a full-stack prototype with:

- a FastAPI backend that handles auth, sessions, and agent orchestration
- a React + Vite frontend that provides a conversational UI
- a Gemini-powered agent that decides which GCP tools to call
- a dynamic tool-loading layer that automatically discovers and registers backend tools
- a confirmation workflow for mutating operations such as VM restarts

The experience is intentionally simple: the user signs in, picks a project, and chats with the agent. The backend translates the request into tool calls, executes them against Google Cloud, and returns a concise ops-style response.

---

## High-level architecture

The system is composed of four main layers:

1. Frontend UI
   - The React app renders the chat experience, project selector, login/logout controls, and confirmation prompts.

2. API layer
   - FastAPI exposes endpoints for auth, session status, project selection, chat, and confirmation.

3. Agent orchestration layer
   - The backend agent sends the user's request and project context to Gemini.
   - Gemini decides which tools to invoke based on the prompt.
   - The agent collects results and formats them into a user-friendly reply.

4. Google Cloud tool layer
   - Tool modules call GCP APIs with the user's OAuth credentials.
   - These include Compute Engine, GKE, Cloud SQL, Monitoring, and Logging.

A simplified flow looks like this:

```text
User -> React frontend -> FastAPI routes -> Gemini agent -> Tool modules -> GCP APIs
                                      ^                                |
                                      |                                |
                                      +---- confirmation flow <------+
```

---

## Key features

### 1. User-scoped Google OAuth

The app uses Google OAuth2 so each visitor authenticates with their own Google account. The backend stores the OAuth tokens server-side in an in-memory session store, and the browser only receives an opaque session cookie. This avoids shipping a shared service account credential to the client.

### 2. Dynamic tool loading

A major architectural improvement is the dynamic tool-loader system:

- the backend discovers tool modules under the tools package automatically
- each tool function is registered via a decorator in the tool registry
- the agent reads the registered tools and exposes them to Gemini as function declarations
- adding a new tool usually means creating a new tool module and decorating a function, without rewriting the core agent loop

This makes the system extensible and keeps the agent logic separate from the tool implementations.

### 3. Frontend chat experience

The React frontend provides:

- sign-in and sign-out flows
- a project picker after authentication
- a chat log for user and agent messages
- a confirmation bar for destructive actions
- a CPU utilization visualization panel for returned monitoring data
- a dedicated incident-summary card that surfaces a structured snapshot of resources, alerts, and recommended next steps when the user asks for an incident summary

### 4. Confirmation before mutations

Mutating actions such as restarting a VM are intentionally gated. The agent does not execute them immediately. Instead it asks for confirmation, and the request only proceeds if the user explicitly confirms it in the UI.

When a command like "restart the VM named app-server-01" is requested, the app prompts:

```text
Confirm restart of VM app-server-01 in zone <zone>? Reply Yes to proceed or Cancel to abort.
```

This is a safety measure designed to prevent accidental infrastructure changes.

### 5. Multi-tool execution and resilience

The agent can invoke multiple independent tools in one turn (for example computing summary data from Compute, GKE, SQL, and alerts). It executes those calls concurrently to reduce latency. It also has model-fallback logic for transient Gemini API errors, quota issues, and model availability problems.

### 6. Incident summary mode

A new incident-summary experience is available for users who want a more operational view of the current environment. If the prompt contains phrases such as “incident summary”, “summarize the incident”, or “service health”, the backend gathers data from Compute Engine, GKE, Cloud SQL, and recent alerts, then returns a structured summary with:

- a project-level heading
- a list of the most relevant resources and their states
- recent alert findings
- recommended next steps

This makes the app feel more like an AIOps copilot than a simple Q&A interface.

---

## Repository structure

```text
.
├── Dockerfile
├── README.md
├── backend/
│   ├── agent.py
│   ├── auth.py
│   ├── config.py
│   ├── main.py
│   ├── requirements.txt
│   ├── session_store.py
│   ├── tool_loader.py
│   ├── tool_specs.py
│   ├── scripts/
│   │   └── simulate_chat.py
│   └── tools/
│       ├── __init__.py
│       ├── compute.py
│       ├── gke.py
│       ├── logs_alerts.py
│       ├── monitoring.py
│       ├── projects.py
│       └── sql.py
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── App.jsx
        ├── main.jsx
        └── style.css
```

---

## File-by-file overview

### Root files

- Dockerfile: containerizes the app for deployment. It installs Python dependencies, copies the backend and frontend, and runs the FastAPI app on port 8080.
- README.md: project overview, setup, architecture notes, and usage guidance.

### Backend files

- backend/main.py: the FastAPI application entrypoint. It wires up auth, health/status endpoints, chat endpoints, project selection, and serves the built frontend static files.
- backend/agent.py: the core orchestration layer. It talks to Gemini, converts tool requests into function calls, dispatches tools, manages confirmation flows, and formats replies.
- backend/auth.py: handles the Google OAuth2 login and callback flow. It builds the OAuth authorization URL, exchanges the code for tokens, and stores a session object.
- backend/config.py: loads environment variables and centralizes settings such as Gemini credentials, OAuth client details, redirect URIs, and session options.
- backend/session_store.py: simple in-memory session storage for OAuth credentials and project selection. This is intentionally lightweight for the prototype stage.
- backend/tool_loader.py: dynamically imports tool modules under the backend.tools package so the registry is populated at runtime.
- backend/tool_specs.py: turns the registered tool metadata into the function declaration schema exposed to Gemini.
- backend/scripts/simulate_chat.py: a small utility script for exercising the chat flow locally without using the UI.

### Backend tool modules

- backend/tools/__init__.py: defines the shared tool registry and the decorator used by all tools.
- backend/tools/compute.py: Compute Engine integration for listing VMs and restarting them. This is where the restart action is implemented.
- backend/tools/gke.py: GKE cluster listing and health inspection.
- backend/tools/logs_alerts.py: Cloud Logging-based alert summarization for warning-or-higher entries.
- backend/tools/monitoring.py: Cloud Monitoring integration for CPU utilization time series.
- backend/tools/projects.py: lists active GCP projects accessible to the signed-in user.
- backend/tools/sql.py: Cloud SQL instance inspection and basic high-CPU detection.

### Frontend files

- frontend/index.html: the base HTML shell used by Vite.
- frontend/package.json: frontend scripts and dependencies.
- frontend/vite.config.js: Vite configuration for local development and build output.
- frontend/src/App.jsx: the main React UI. It handles authentication state, project selection, chat submission, pending action confirmation, and chart rendering.
- frontend/src/main.jsx: React entrypoint that mounts the app into the DOM.
- frontend/src/style.css: styling for the chat UI, auth area, project picker, confirmation bar, and CPU chart.

---

## Local setup

### 1. Prerequisites

You will need:

- Python 3.11+
- Node.js and npm
- a Google Cloud project
- a Gemini API key from Google AI Studio
- OAuth credentials from Google Cloud Console

### 2. Backend dependencies

From the repository root:

```bash
cd backend
pip install -r requirements.txt
```

### 3. Environment variables

Create a .env file in the repository root with the following variables:

```env
GEMINI_API_KEY=your_gemini_key
GOOGLE_CLIENT_ID=your_google_oauth_client_id
GOOGLE_CLIENT_SECRET=your_google_oauth_client_secret
SESSION_SECRET=some_long_random_string
OAUTH_REDIRECT_URI=http://localhost:8000/auth/callback
FRONTEND_ORIGIN=http://localhost:8000
```

### 4. Google OAuth setup

In Google Cloud Console:

- create an OAuth 2.0 Client ID
- choose a Web application type
- add the redirect URI:

```text
http://localhost:8000/auth/callback
```

The app uses the broad cloud-platform scope for this prototype, which allows it to access Compute Engine, GKE, Cloud SQL, Monitoring, and Logging with one consent screen.

### 5. Run the frontend

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server will usually run at:

```text
http://localhost:3000
```

### 6. Run the backend

From the backend folder:

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Then open:

```text
http://localhost:8000
```

If you want the backend to serve the built React frontend, build the frontend first:

```bash
cd frontend
npm run build
```

Then start the backend again from the backend directory.

---

## Required permissions and safety model

The signed-in Google account must have the relevant IAM roles on the target project. Typical examples include:

- Compute Viewer or Compute Instance Admin for VM inspection and restart
- Kubernetes Engine Viewer for GKE cluster information
- Cloud SQL Viewer for Cloud SQL inventory
- Monitoring Viewer for CPU metrics
- Logs Viewer for alert summaries

For mutating actions like VM restart, the app does not execute the operation immediately. It asks the user to confirm the action in the frontend. The user must explicitly approve it before the backend sends the restart request to Google Cloud.

This is important because the restart operation is real, can interrupt workloads, and should only be used after the user clearly intends it.

---

## Tech stack

### Backend

- Python 3.11
- FastAPI
- Uvicorn
- Google GenAI SDK
- Google Auth libraries
- Google Cloud Python client libraries
- Pydantic
- python-dotenv
- httpx

### Frontend

- React 18
- Vite
- JavaScript/JSX
- CSS

### Infrastructure / deployment

- Docker
- Google Cloud APIs

---

## Current limitations and prototype notes

This is intentionally a working prototype, not a production-hardened operations platform. A few scope cuts are worth noting:

- sessions are stored in memory only, so they do not persist across process restarts
- the OAuth scope is broad for simplicity and to reduce setup friction
- alerting is currently approximated from Cloud Logging severity rather than a full Monitoring alerting-policy integration
- the app relies on the browser session and server-side token storage, which is suitable for a local prototype but would need a more durable store and stronger operational controls for production deployment

---

## Example prompts

You can try prompts such as:

- "List all Compute Engine VM instances"
- "Show CPU utilization for production VMs"
- "List unhealthy Kubernetes clusters"
- "Summarize infrastructure alerts from the last 24 hours"
- "Give me an incident summary"
- "Summarize the current incident"
- "Restart the VM named app-server-01"
- "List Cloud SQL instances with high CPU usage"

---

## Summary

AIOps Agent is a prototype for natural-language infrastructure operations on Google Cloud. It combines a React frontend, a FastAPI backend, Gemini-driven orchestration, and user-scoped GCP access to offer a practical chat-based experience for inspection, monitoring, and safe approval-based actions.
