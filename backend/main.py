import logging
import os

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel

try:
    from .config import settings
    from .session_store import get_session, update_session
    from .auth import router as auth_router, get_credentials_from_session
    from .tools.projects import list_projects
    from . import agent
except Exception:
    from config import settings
    from session_store import get_session, update_session
    from auth import router as auth_router, get_credentials_from_session
    from tools.projects import list_projects
    import agent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("aiops-agent")

app = FastAPI(title="AIOps Agent for Cloud Infrastructure")
app.include_router(auth_router)


@app.get("/debug/model")
def debug_model():
    """Return the configured GEMINI model and any environment override."""
    import os

    return {"GEMINI_MODEL": settings.GEMINI_MODEL, "GEMINI_MODEL_env": os.getenv("GEMINI_MODEL")}


def _require_session(request: Request) -> dict:
    cookie_value = request.cookies.get(settings.SESSION_COOKIE_NAME)
    session = get_session(cookie_value)
    if session is None:
        raise HTTPException(status_code=401, detail="Not signed in. Please log in with Google first.")
    return session


@app.get("/api/status")
def status(request: Request):
    cookie_value = request.cookies.get(settings.SESSION_COOKIE_NAME)
    session = get_session(cookie_value)
    if session is None:
        return {"signed_in": False}
    return {
        "signed_in": True,
        "email": session.get("email"),
        "project_id": session.get("project_id"),
    }


@app.get("/api/projects")
def projects(request: Request):
    session = _require_session(request)
    credentials = get_credentials_from_session(session)
    result = list_projects(credentials)
    return {"projects": result}


class SelectProjectBody(BaseModel):
    project_id: str


@app.post("/api/select-project")
def select_project(body: SelectProjectBody, request: Request):
    session = _require_session(request)
    cookie_value = request.cookies.get(settings.SESSION_COOKIE_NAME)
    update_session(cookie_value, project_id=body.project_id)
    return {"project_id": body.project_id}


class ChatBody(BaseModel):
    message: str


@app.post("/api/chat")
def chat(body: ChatBody, request: Request):
    session = _require_session(request)
    credentials = get_credentials_from_session(session)
    project_id = session.get("project_id")

    try:
        reply = agent.handle_message(body.message, credentials, project_id)
    except Exception as e:
        logger.exception("Agent error while handling chat message")
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")

    return {"reply": reply}


# Serve the built React frontend last, so /api and /auth routes above take precedence.
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
frontend_build_dir = os.path.join(frontend_dir, "dist")
if not os.path.isdir(frontend_build_dir):
    logger.warning("Frontend build directory not found. Run `npm run build` in frontend/ before using backend static serving.")
app.mount("/", StaticFiles(directory=frontend_build_dir, html=True), name="frontend")
