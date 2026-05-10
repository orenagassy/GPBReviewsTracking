# Setup Guide — GBP Reviews Tracker

This guide covers everything from creating your Google Cloud project to deploying a live SaaS on Streamlit Community Cloud for free.

---

## Prerequisites

- Python 3.11+
- A Google account that manages at least one Google Business Profile location
- A GitHub account (for free Streamlit Community Cloud deployment)

---

## Step 1 — Google Cloud Project

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Click **Select a project → New Project**
3. Give it a name (e.g. `gbp-reviews-tracker`) and click **Create**
4. Make sure the new project is selected in the top dropdown

---

## Step 2 — Enable the Business Profile API

1. In the Cloud Console, go to **APIs & Services → Library**
2. Search for **"Business Profile API"** (also called "My Business")
3. Enable the following APIs:
   - **Business Profile Performance API** *(for the management APIs)*
   - **My Business Account Management API** *(lists accounts and locations)*
   - **My Business Reviews API** *(fetches review data)*

> **Tip:** If you search for "My Business" all relevant APIs appear together.

---

## Step 3 — Configure OAuth Consent Screen

1. Go to **APIs & Services → OAuth consent screen**
2. Select **External** (required for any Google account to sign in)
3. Fill in the required fields:
   - **App name**: GBP Reviews Tracker *(or your brand name)*
   - **User support email**: your email
   - **Developer contact email**: your email
4. Click **Save and Continue**
5. On the **Scopes** step, add the scope:
   - `https://www.googleapis.com/auth/business.manage`
6. On the **Test users** step, add your own Google account email
   - Until the app is verified by Google, only listed test users can sign in
7. Click **Save and Continue → Back to Dashboard**

> **Production verification (optional):** If you want anyone to sign in (not just test users), submit the app for Google verification. For personal/team use, staying in "Testing" mode is sufficient.

---

## Step 4 — Create OAuth 2.0 Credentials

1. Go to **APIs & Services → Credentials → Create Credentials → OAuth client ID**
2. Application type: **Web application**
3. Name: `GBP Reviews Tracker`
4. **Authorized redirect URIs** — add:
   - `http://localhost:8501` *(for local development)*
   - `https://your-app-name.streamlit.app` *(for production — add after deployment)*
5. Click **Create**
6. Copy the **Client ID** and **Client Secret** — you'll need these next

---

## Step 5 — Local Development Setup

### Install dependencies
```bash
pip install -r requirements.txt
```

### Configure secrets
```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Edit `.streamlit/secrets.toml`:
```toml
[google]
client_id = "your-client-id.apps.googleusercontent.com"
client_secret = "your-client-secret"
redirect_uri = "http://localhost:8501"
```

> `secrets.toml` is gitignored. Never commit it.

### Run locally
```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser. Click **Sign in with Google**, complete the OAuth flow, then pick your account, location, and generate a report.

---

## Step 6 — Deploy to Streamlit Community Cloud (Free)

Streamlit Community Cloud hosts public and private Streamlit apps for free.

### 6.1 Push code to GitHub

Make sure your repo is on GitHub (this project is already configured for it). The `.gitignore` excludes `secrets.toml` — confirm that before pushing.

```bash
git push origin main
```

### 6.2 Create the app on Streamlit Community Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub
2. Click **New app**
3. Select your repository: `orenagassy/GPBReviewsTracking`
4. Branch: `main`
5. Main file path: `app.py`
6. Click **Deploy**

### 6.3 Add secrets to Streamlit Cloud

In the app settings on Streamlit Cloud:

1. Click **⋮ → Settings → Secrets**
2. Paste your secrets in TOML format:

```toml
[google]
client_id = "your-client-id.apps.googleusercontent.com"
client_secret = "your-client-secret"
redirect_uri = "https://your-app-name.streamlit.app"
```

> Use the **actual Streamlit app URL** as `redirect_uri` — find it in the Streamlit Cloud dashboard after deployment.

### 6.4 Update GCP authorized redirect URI

1. Go back to **Google Cloud Console → APIs & Services → Credentials**
2. Edit your OAuth 2.0 client
3. Add the Streamlit app URL to **Authorized redirect URIs**:
   ```
   https://your-app-name.streamlit.app
   ```
4. Click **Save**

Your app is now live and free. Share the Streamlit URL with anyone who has GBP access — they sign in with their own Google account and see their own properties.

---

## Step 7 — Multi-user SaaS Notes

When running in "Testing" mode on OAuth consent screen, only explicitly listed test users can sign in. To open it to any Google account:

1. Go to **OAuth consent screen → Publish App**
2. Submit for Google verification (required for the `business.manage` scope)
3. Google reviews the app (takes a few days to weeks)
4. Once approved, any Google account that manages a GBP location can sign in

Until verified, add each user's Google email to the **Test users** list in the consent screen.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `redirect_uri_mismatch` error | The `redirect_uri` in `secrets.toml` must exactly match what's in GCP Credentials (including `http` vs `https`) |
| `Access blocked: app not verified` | Add your email to Test users in OAuth consent screen |
| No accounts or locations appear | The signed-in Google account must be an owner/manager of at least one GBP location |
| `403 Forbidden` on reviews API | Ensure all three Business Profile APIs are enabled in GCP |
| Token expired error | Sign out and sign back in — the app refreshes tokens automatically but may fail if the refresh token was revoked |

---

## Changing the default date range

Edit `config.yaml`:
```yaml
report:
  default_months_back: 2   # change this
  max_months_back: 24
```

The user can also adjust it interactively in the sidebar without touching code.
