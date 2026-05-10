import base64
import hashlib
import json
import secrets
import streamlit as st
from pathlib import Path
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES = [
    "https://www.googleapis.com/auth/business.manage",
    "openid",
    "email",
    "profile",
]

# PKCE verifier is written here by get_auth_url() and consumed by exchange_code().
# Must survive the browser round-trip to Google (session_state is reset on redirect),
# so a file is used instead of session_state. Gitignored.
_PKCE_FILE = Path(".streamlit") / "pkce_verifier.txt"


def _client_config() -> dict:
    return {
        "web": {
            "client_id": st.secrets["google"]["client_id"],
            "client_secret": st.secrets["google"]["client_secret"],
            "redirect_uris": [st.secrets["google"]["redirect_uri"]],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }


def _make_challenge(verifier: str) -> str:
    return base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")


def get_auth_url() -> str:
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES)
    flow.redirect_uri = st.secrets["google"]["redirect_uri"]

    # Reuse the verifier if the login page rerenders — overwriting it would break
    # any in-flight token exchange if the user has already clicked "Sign in".
    if "oauth_verifier" not in st.session_state:
        verifier = secrets.token_urlsafe(32)
        st.session_state["oauth_verifier"] = verifier
        _PKCE_FILE.write_text(verifier, encoding="utf-8")
    else:
        verifier = st.session_state["oauth_verifier"]

    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        code_challenge=_make_challenge(verifier),
        code_challenge_method="S256",
    )
    st.session_state["oauth_state"] = state
    return auth_url


def exchange_code(code: str, state: str) -> str:
    """Exchange OAuth authorization code for credentials. Returns credentials JSON."""
    stored_state = st.session_state.get("oauth_state")
    if stored_state and state != stored_state:
        raise ValueError(
            f"OAuth state mismatch — stored={stored_state!r}, received={state!r}"
        )

    verifier = None
    try:
        verifier = _PKCE_FILE.read_text(encoding="utf-8").strip()
        _PKCE_FILE.unlink()
    except FileNotFoundError:
        pass

    flow = Flow.from_client_config(_client_config(), scopes=SCOPES)
    flow.redirect_uri = st.secrets["google"]["redirect_uri"]
    flow.fetch_token(code=code, code_verifier=verifier)
    return flow.credentials.to_json()


def get_valid_credentials(credentials_json: str) -> tuple[Credentials, str]:
    """Return (credentials, credentials_json). Refreshes the token if expired."""
    creds = Credentials.from_authorized_user_info(json.loads(credentials_json))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        credentials_json = creds.to_json()
    return creds, credentials_json
