"""
Google OAuth2 flow so each visitor connects THEIR OWN GCP project --
no shared service-account credentials ever live on the server.
"""
import json
import secrets

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials

try:
    from .config import settings
    from .session_store import create_session, get_session, update_session, delete_session
except Exception:
    from config import settings
    from session_store import create_session, get_session, update_session, delete_session

router = APIRouter()

_STATE_COOKIE = "aiops_oauth_state"


def _build_flow() -> Flow:
    client_config = {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.OAUTH_REDIRECT_URI],
        }
    }
    return Flow.from_client_config(
        client_config, scopes=settings.GOOGLE_SCOPES, redirect_uri=settings.OAUTH_REDIRECT_URI
    )


@router.get("/auth/login")
def login():
    flow = _build_flow()
    state = secrets.token_urlsafe(16)
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    resp = RedirectResponse(auth_url)
    resp.set_cookie(_STATE_COOKIE, state, httponly=True, max_age=600, samesite="lax")
    return resp


@router.get("/auth/callback")
def callback(request: Request, code: str = None, state: str = None, error: str = None):
    if error:
        return RedirectResponse(f"{settings.FRONTEND_ORIGIN}/?auth_error={error}")

    expected_state = request.cookies.get(_STATE_COOKIE)
    if not code or not state or state != expected_state:
        return RedirectResponse(f"{settings.FRONTEND_ORIGIN}/?auth_error=invalid_state")

    flow = _build_flow()
    flow.fetch_token(code=code)
    creds = flow.credentials

    # Fetch the user's email just for display in the UI.
    email = None
    try:
        with httpx.Client(timeout=10) as client:
            r = client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {creds.token}"},
            )
            if r.status_code == 200:
                email = r.json().get("email")
    except httpx.HTTPError:
        pass

    session_data = {
        "credentials": {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": creds.scopes,
        },
        "email": email,
        "project_id": None,
    }
    cookie_value = create_session(session_data)

    resp = RedirectResponse(f"{settings.FRONTEND_ORIGIN}/")
    resp.delete_cookie(_STATE_COOKIE)
    resp.set_cookie(
        settings.SESSION_COOKIE_NAME,
        cookie_value,
        httponly=True,
        max_age=settings.SESSION_TTL_SECONDS,
        samesite="lax",
    )
    return resp


@router.post("/auth/logout")
def logout(request: Request):
    cookie_value = request.cookies.get(settings.SESSION_COOKIE_NAME)
    delete_session(cookie_value)
    resp = Response(status_code=204)
    resp.delete_cookie(settings.SESSION_COOKIE_NAME)
    return resp


def get_credentials_from_session(session: dict) -> Credentials:
    """Rebuild a google.oauth2.credentials.Credentials object from stored session data."""
    c = session["credentials"]
    return Credentials(
        token=c["token"],
        refresh_token=c["refresh_token"],
        token_uri=c["token_uri"],
        client_id=c["client_id"],
        client_secret=c["client_secret"],
        scopes=c["scopes"],
    )
