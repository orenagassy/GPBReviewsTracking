import base64
import hashlib
import json
import secrets
import streamlit as st
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES = [
    "https://www.googleapis.com/auth/business.manage",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid",
]


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


def _strip_secret(creds_json: str) -> str:
    """Remove client_secret from persisted credential blob.
    It is injected at runtime from st.secrets — never needs to be stored."""
    data = json.loads(creds_json)
    data.pop("client_secret", None)
    return json.dumps(data)


def get_auth_url() -> str:
    """Return a Google OAuth URL. Encodes the PKCE verifier in the state
    parameter so it survives the browser redirect without file I/O and
    works correctly under multi-user / multi-worker deployments."""
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES)
    flow.redirect_uri = st.secrets["google"]["redirect_uri"]

    verifier = secrets.token_urlsafe(32)
    # state = "{nonce}:{verifier}" — nonce provides entropy, verifier is extracted
    # in exchange_code() after the redirect brings it back in the callback URL.
    state = f"{secrets.token_urlsafe(16)}:{verifier}"

    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
        code_challenge=_make_challenge(verifier),
        code_challenge_method="S256",
    )
    return auth_url


def exchange_code(code: str, state: str) -> str:
    """Exchange OAuth authorization code for credentials. Returns credentials JSON
    with client_secret stripped — it is never persisted to disk."""
    if not state or ":" not in state:
        raise ValueError("OAuth state missing or malformed — restart the sign-in flow")

    _, verifier = state.split(":", 1)
    if not verifier:
        raise ValueError("PKCE verifier missing from state — restart the sign-in flow")

    flow = Flow.from_client_config(_client_config(), scopes=SCOPES)
    flow.redirect_uri = st.secrets["google"]["redirect_uri"]
    flow.fetch_token(code=code, code_verifier=verifier)
    return _strip_secret(flow.credentials.to_json())


def get_valid_credentials(credentials_json: str) -> tuple[Credentials, str]:
    """Return (credentials, credentials_json). Refreshes the token if expired.
    Injects client_secret from st.secrets — it is not stored in the JSON blob."""
    data = json.loads(credentials_json)
    data["client_secret"] = st.secrets["google"]["client_secret"]
    creds = Credentials.from_authorized_user_info(data)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        credentials_json = _strip_secret(creds.to_json())
    return creds, credentials_json
