import requests
from google.oauth2.credentials import Credentials
from auth import get_valid_credentials

_ACCOUNT_BASE = "https://mybusinessaccountmanagement.googleapis.com/v1"
_REVIEWS_BASE = "https://mybusinessreviews.googleapis.com/v1"


def _auth_header(creds: Credentials) -> dict:
    return {"Authorization": f"Bearer {creds.token}"}


def _raise(resp: requests.Response) -> None:
    """Raise HTTPError with Google's error detail included in the message."""
    if not resp.ok:
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text
        raise requests.HTTPError(
            f"{resp.status_code} {resp.reason}: {detail}", response=resp
        )


def get_accounts(credentials_json: str) -> tuple[list[dict], str]:
    """Return (accounts, updated_credentials_json)."""
    creds, credentials_json = get_valid_credentials(credentials_json)
    resp = requests.get(f"{_ACCOUNT_BASE}/accounts", headers=_auth_header(creds))
    _raise(resp)
    return resp.json().get("accounts", []), credentials_json


def get_locations(credentials_json: str, account_name: str) -> tuple[list[dict], str]:
    """Return (locations, updated_credentials_json). account_name: 'accounts/123'."""
    creds, credentials_json = get_valid_credentials(credentials_json)
    resp = requests.get(
        f"{_ACCOUNT_BASE}/{account_name}/locations",
        headers=_auth_header(creds),
    )
    _raise(resp)
    return resp.json().get("locations", []), credentials_json


def get_reviews(
    credentials_json: str, location_name: str, page_size: int = 50
) -> tuple[list[dict], str]:
    """Fetch all reviews for a location (paginated). location_name: 'accounts/.../locations/...'."""
    creds, credentials_json = get_valid_credentials(credentials_json)
    reviews: list[dict] = []
    page_token: str | None = None

    while True:
        params: dict = {"pageSize": page_size}
        if page_token:
            params["pageToken"] = page_token

        resp = requests.get(
            f"{_REVIEWS_BASE}/{location_name}/reviews",
            headers=_auth_header(creds),
            params=params,
        )
        _raise(resp)
        data = resp.json()
        reviews.extend(data.get("reviews", []))

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return reviews, credentials_json
