from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # Streamlit Cloud usually uses st.secrets rather than .env files.
    pass


def _secret(name: str, default=None):
    """Read config from Streamlit secrets when deployed, else environment variables."""
    try:
        import streamlit as st

        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name, default)


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(_secret("SQLITE_DB_PATH", str(BASE_DIR / "admin_alpha_hosted.db")))
APP_ENV = _secret("APP_ENV", "hosted_alpha")

# Keep Gmail scopes minimal for the first alpha.
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Local desktop OAuth path. Used only by older/local alpha code if present.
GOOGLE_CLIENT_SECRETS_FILE = Path(
    _secret("GOOGLE_CLIENT_SECRETS_FILE", str(BASE_DIR / "client_secret.json"))
)

# Hosted web OAuth settings. These must be added in Streamlit Cloud secrets.
GOOGLE_CLIENT_ID = _secret("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = _secret("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = _secret("GOOGLE_REDIRECT_URI")

# Secret used to sign OAuth state values in the hosted flow.
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
OAUTH_STATE_SECRET = (
    _secret("OAUTH_STATE_SECRET")
    or _secret("TOKEN_ENCRYPTION_KEY")
    or "dev-only-change-me"
)

# Optional but recommended. If set to a Fernet key, Gmail credentials are encrypted before saving to SQLite.
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
TOKEN_ENCRYPTION_KEY = _secret("TOKEN_ENCRYPTION_KEY")
