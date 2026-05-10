# CLAUDE.md — GBP Reviews Tracker

## Project Overview
Streamlit web app that authenticates users via Google OAuth 2.0, fetches Google Business Profile (GBP) review data from the Google Business Profile API, and renders a configurable weekly breakdown report (two Plotly charts + a detail table).

## File Map
| File | Purpose |
|---|---|
| `app.py` | Main Streamlit app — OAuth callback handling, account/location pickers, report UI |
| `auth.py` | Google OAuth2 flow: `get_auth_url`, `exchange_code`, `get_valid_credentials` |
| `gbp_api.py` | GBP REST API calls: accounts, locations, reviews (paginated) |
| `report.py` | Weekly aggregation of review dicts into a pandas DataFrame |
| `config.yaml` | All non-secret configurable values |
| `.streamlit/secrets.toml` | Google client_id, client_secret, redirect_uri — **gitignored, never commit** |

## Core Rules

### Config first
Every threshold, label, color, and default belongs in `config.yaml`. No hardcoded string literals or magic numbers in Python.

### Secrets separation
`secrets.toml` holds only OAuth credentials. Nothing sensitive goes in `config.yaml` or source files.

### Data integrity
Report values are derived exclusively from GBP API responses. Never substitute estimates or fill missing data with industry averages — surface gaps explicitly.

### Surgical changes
Touch only what the task requires. Match existing style. Do not refactor adjacent code.

### Defensive programming
Validate at API response boundaries. Use `.get()` with defaults. Check for empty DataFrames before computing.

## GBP API Endpoints
| Endpoint | Purpose |
|---|---|
| `GET https://mybusinessaccountmanagement.googleapis.com/v1/accounts` | List GBP accounts |
| `GET https://mybusinessaccountmanagement.googleapis.com/v1/{account}/locations` | List locations |
| `GET https://mybusinessreviews.googleapis.com/v1/{location}/reviews` | Fetch reviews (paginated) |

OAuth scope required: `https://www.googleapis.com/auth/business.manage`

## Session State Keys
| Key | Value |
|---|---|
| `credentials` | JSON string from `Credentials.to_json()` |
| `oauth_state` | CSRF state token from `get_auth_url()` |
| `accounts` | Cached list of GBP account dicts |
| `locations_{account_name}` | Cached locations per account |

## Local Dev
```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Fill in client_id, client_secret, redirect_uri
streamlit run app.py
```
