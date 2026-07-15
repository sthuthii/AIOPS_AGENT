"""
Central configuration for the AIOps Agent backend.
All values are read from environment variables so no secrets are ever
hard-coded or committed to source control.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # --- Gemini (the agent's "brain") ---
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # --- Google OAuth (lets each visitor connect their OWN GCP project) ---
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    OAUTH_REDIRECT_URI: str = os.getenv(
        "OAUTH_REDIRECT_URI", "http://localhost:8000/auth/callback"
    )

    # Scopes requested from the user. `cloud-platform` is broad on purpose
    # for this prototype (it covers Compute, GKE, Cloud SQL, Monitoring and
    # Logging with a single consent screen). See README "Limitations" for
    # how to narrow this for a production deployment.
    GOOGLE_SCOPES = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/cloud-platform",
    ]

    # --- Session signing (server keeps the real tokens; browser only gets
    # a signed, opaque session id cookie) ---
    SESSION_SECRET: str = os.getenv("SESSION_SECRET", "dev-secret-change-me")
    SESSION_COOKIE_NAME: str = "aiops_session"
    SESSION_TTL_SECONDS: int = int(os.getenv("SESSION_TTL_SECONDS", "3600"))

    # --- Misc ---
    FRONTEND_ORIGIN: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:8000")
    ENV: str = os.getenv("ENV", "development")


settings = Settings()
