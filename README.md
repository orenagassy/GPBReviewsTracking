# GBP Reviews Tracker

A free, self-hosted Streamlit web app that connects to your Google Business Profile, pulls all reviews for a location, and generates a weekly breakdown report.

## What it does

1. Sign in with Google (OAuth 2.0)
2. Pick a GBP account and location from your connected properties
3. Set how many months back to analyse (default: 2)
4. Get an instant report with:
   - **Bar chart** — weekly review count
   - **Line chart** — weekly average rating
   - **Detail table** — week-by-week breakdown

## Quick start

See [SETUP.md](SETUP.md) for the full setup guide including Google Cloud configuration and SaaS deployment.

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# fill in your Google OAuth credentials
streamlit run app.py
```

## Tech stack

| Layer | Tool |
|---|---|
| UI | [Streamlit](https://streamlit.io) |
| Charts | [Plotly](https://plotly.com/python/) |
| Data | [pandas](https://pandas.pydata.org/) |
| Auth | google-auth-oauthlib |
| Hosting | [Streamlit Community Cloud](https://streamlit.io/cloud) (free) |
