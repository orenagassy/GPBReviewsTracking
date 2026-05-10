import json
import streamlit as st
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES = [
    "https://www.googleapis.com/auth/business.manage",
    "openid",
    "email",
    "profile",
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


def get_auth_url() -> str:
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES)
    flow.redirect_uri = st.secrets["google"]["redirect_uri"]
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    st.session_state["oauth_state"] = state
    return auth_url


def exchange_code(code: str, state: str) -> str:
    """Exchange OAuth authorization code for credentials. Returns credentials JSON."""
    stored_state = st.session_state.get("oauth_state")
    flow = Flow.from_client_config(
        _client_config(),
        scopes=SCOPES,
        state=stored_state,
    )
    flow.redirect_uri = st.secrets["google"]["redirect_uri"]
    flow.fetch_token(code=code)
    return flow.credentials.to_json()


def get_valid_credentials(credentials_json: str) -> tuple[Credentials, str]:
    """Return (credentials, credentials_json). Refreshes the token if expired."""
    creds = Credentials.from_authorized_user_info(json.loads(credentials_json))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        credentials_json = creds.to_json()
    return creds, credentials_json
