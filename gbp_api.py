import re
import requests
from google.oauth2.credentials import Credentials
from auth import get_valid_credentials

_ACCOUNT_BASE = "https://mybusinessaccountmanagement.googleapis.com/v1"
_REVIEWS_BASE = "https://mybusiness.googleapis.com/v4"
_RESOURCE_RE = re.compile(r"^[a-zA-Z]+/\d+(/[a-zA-Z]+/\d+)*$")
_TIMEOUT = 30


def _auth_header(creds: Credentials) -> dict:
    return {"Authorization": f"Bearer {creds.token}"}


def _validate(name: str) -> str:
    if not _RESOURCE_RE.match(name):
        raise ValueError(f"Invalid resource name: {name!r}")
    return name


def _raise(resp: requests.Response) -> None:
    """Raise HTTPError with Google's error detail included."""
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
    resp = requests.get(
        f"{_ACCOUNT_BASE}/accounts", headers=_auth_header(creds), timeout=_TIMEOUT
    )
    _raise(resp)
    return resp.json().get("accounts", []), credentials_json


def get_locations(credentials_json: str, account_name: str) -> tuple[list[dict], str]:
    """Return (locations, updated_credentials_json). account_name: 'accounts/123'."""
    creds, credentials_json = get_valid_credentials(credentials_json)
    resp = requests.get(
        f"{_ACCOUNT_BASE}/{_validate(account_name)}/locations",
        headers=_auth_header(creds),
        params={"readMask": "name,title"},
        timeout=_TIMEOUT,
    )
    _raise(resp)
    return resp.json().get("locations", []), credentials_json


def get_reviews(
    credentials_json: str,
    location_name: str,
    page_size: int = 50,
    max_pages: int = 20,
) -> tuple[list[dict], str]:
    """Fetch all reviews for a location (paginated). location_name: 'accounts/.../locations/...'."""
    creds, credentials_json = get_valid_credentials(credentials_json)
    reviews: list[dict] = []
    page_token: str | None = None

    for _ in range(max_pages):
        params: dict = {"pageSize": page_size}
        if page_token:
            params["pageToken"] = page_token

        resp = requests.get(
            f"{_REVIEWS_BASE}/{_validate(location_name)}/reviews",
            headers=_auth_header(creds),
            params=params,
            timeout=_TIMEOUT,
        )
        _raise(resp)
        data = resp.json()
        reviews.extend(data.get("reviews", []))

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return reviews, credentials_json
