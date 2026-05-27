import os
import logging
import yaml
import streamlit as st
from pathlib import Path
from datetime import date
from dateutil.relativedelta import relativedelta

from auth import get_auth_url, exchange_code
from gbp_api import get_accounts, get_locations, get_reviews
from report import build_weekly_report

_CREDS_FILE = Path(".streamlit") / "cached_creds.json"
_log = logging.getLogger(__name__)


@st.cache_data
def load_config() -> dict:
    with open("config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _debug(config: dict) -> bool:
    return bool(config.get("debug_mode"))


def _dbg(msg: str, config: dict) -> None:
    if _debug(config):
        st.info(f"🔍 {msg}")


def _save_creds(creds_json: str) -> None:
    try:
        if _CREDS_FILE.read_text(encoding="utf-8") == creds_json:
            return
    except OSError:
        pass
    _CREDS_FILE.write_text(creds_json, encoding="utf-8")
    try:
        os.chmod(_CREDS_FILE, 0o600)
    except OSError:
        pass


def _load_creds() -> str | None:
    try:
        return _CREDS_FILE.read_text(encoding="utf-8")
    except OSError:
        return None


def _clear_creds() -> None:
    _CREDS_FILE.unlink(missing_ok=True)


_STAR_INT = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5}


def _generate_insights(low_reviews: list[dict], api_key: str) -> str:
    import anthropic

    lines = []
    for r in low_reviews[:60]:
        stars = _STAR_INT.get(r.get("starRating", ""), "?")
        comment = (r.get("comment") or "").strip()
        if comment:
            lines.append(f"[{stars} stars] {comment}")

    if not lines:
        return f"{len(low_reviews)} low-rated review(s) found, but none contained written comments."

    prompt = (
        f"Below are {len(lines)} customer reviews for a business, each rated 3 stars or below.\n\n"
        + "\n".join(lines)
        + "\n\nWrite a concise insight summary (150–200 words) for the business owner covering:\n"
        "- Main recurring themes or complaints\n"
        "- Specific issues customers mention\n"
        "- Patterns worth acting on\n"
        "Be direct and actionable. Do not add preamble."
    )

    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def show_login(config: dict) -> None:
    st.title(config["ui"]["app_title"])
    st.write(config["ui"]["signin_message"])
    st.link_button("Sign in with Google", get_auth_url(), type="primary")


def show_report(config: dict) -> None:
    import plotly.graph_objects as go
    cfg_report = config["report"]
    cfg_charts = config["charts"]

    st.title(config["ui"]["app_title"])

    with st.sidebar:
        st.header("Report Settings")
        months_back = st.number_input(
            "Months to analyse",
            min_value=1,
            max_value=cfg_report["max_months_back"],
            value=cfg_report["default_months_back"],
            step=1,
        )
        st.divider()
        if st.button("Sign out"):
            _clear_creds()
            st.session_state.clear()
            st.rerun()

    if "accounts_error" in st.session_state:
        st.error(st.session_state["accounts_error"])
        if _debug(config):
            st.info("If the error says quota_limit_value '0', your GCP project has zero quota for mybusinessaccountmanagement.googleapis.com — go to GCP Console → APIs & Services → Quotas and request an increase.")
        if st.button("Retry"):
            del st.session_state["accounts_error"]
            st.rerun()
        return

    if "accounts" not in st.session_state:
        with st.spinner("Loading accounts…"):
            try:
                accounts, creds_json = get_accounts(st.session_state["credentials"])
                st.session_state["credentials"] = creds_json
                _save_creds(creds_json)
                st.session_state["accounts"] = accounts
            except Exception as exc:
                _log.error("Failed to load accounts: %s", exc)
                msg = "Failed to load accounts. Please try again."
                if _debug(config):
                    msg = f"Failed to load accounts: {exc}"
                st.session_state["accounts_error"] = msg
                st.rerun()

    accounts = st.session_state.get("accounts")
    if accounts is None:
        return
    if not accounts:
        st.warning("No Google Business Profile accounts found for this Google account.")
        return

    account_map = {a.get("accountName", a["name"]): a["name"] for a in accounts}
    selected_account_label = st.selectbox("Account", account_map)
    selected_account = account_map[selected_account_label]

    location_key = f"locations_{selected_account}"
    location_error_key = f"locations_error_{selected_account}"

    if location_error_key in st.session_state:
        st.error(st.session_state[location_error_key])
        if st.button("Retry"):
            del st.session_state[location_error_key]
            st.rerun()
        return

    if location_key not in st.session_state:
        with st.spinner("Loading locations…"):
            try:
                locations, creds_json = get_locations(
                    st.session_state["credentials"], selected_account
                )
                st.session_state["credentials"] = creds_json
                _save_creds(creds_json)
                st.session_state[location_key] = locations
            except Exception as exc:
                _log.error("Failed to load locations: %s", exc)
                msg = "Failed to load locations. Please try again."
                if _debug(config):
                    msg = f"Failed to load locations: {exc}"
                st.session_state[location_error_key] = msg
                st.rerun()

    locations = st.session_state.get(location_key)
    if locations is None:
        return
    if not locations:
        st.warning("No locations found for this account.")
        return

    location_map = {loc.get("title", loc["name"]): loc["name"] for loc in locations}
    selected_location_label = st.selectbox("Location", location_map)
    selected_location = location_map[selected_location_label]

    if st.button("Generate Report", type="primary"):
        end_date = date.today()
        start_date = end_date - relativedelta(months=months_back)

        full_location = (
            f"{selected_account}/{selected_location}"
            if selected_location.startswith("locations/")
            else selected_location
        )
        _dbg(f"Fetching reviews for: {full_location}", config)
        with st.spinner("Fetching reviews…"):
            try:
                reviews, creds_json = get_reviews(
                    st.session_state["credentials"],
                    full_location,
                    page_size=cfg_report["page_size"],
                    max_pages=cfg_report["max_review_pages"],
                )
                st.session_state["credentials"] = creds_json
                _save_creds(creds_json)
            except Exception as exc:
                _log.error("Failed to fetch reviews: %s", exc)
                if _debug(config):
                    st.error(f"Failed to fetch reviews: {exc}")
                    st.exception(exc)
                else:
                    st.error("Failed to fetch reviews. Please try again.")
                return

        _dbg(f"Fetched {len(reviews)} total reviews; filtering {start_date} → {end_date}", config)

        df = build_weekly_report(reviews, start_date, end_date)

        total_reviews = int(df["review_count"].sum())
        if total_reviews == 0:
            st.info("No reviews found in this date range.")
            return

        overall_avg = df.loc[df["review_count"] > 0, "avg_rating"].mean()

        st.caption(f"Period: {start_date.strftime('%b %d, %Y')} – {end_date.strftime('%b %d, %Y')}")

        k1, k2 = st.columns(2)
        k1.metric("Total Reviews", total_reviews)
        k2.metric("Overall Avg Rating", f"{overall_avg:.2f} ⭐")

        st.divider()

        from plotly.subplots import make_subplots
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Bar(
                x=df["week_start"],
                y=df["review_count"],
                name="Review Count",
                marker_color=cfg_charts["bar_color"],
            ),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(
                x=df["week_start"],
                y=df["avg_rating"],
                name="Avg Rating",
                mode="lines+markers",
                line=dict(color=cfg_charts["line_color"], width=2),
                connectgaps=False,
            ),
            secondary_y=True,
        )
        fig.update_layout(
            xaxis_title="Week (Monday)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(t=40, b=40),
        )
        fig.update_yaxes(title_text="# Reviews", secondary_y=False)
        fig.update_yaxes(title_text="Avg Rating", range=[0.5, 5.5], tickvals=[1, 2, 3, 4, 5], secondary_y=True)
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Insights: Reviews ≤ 3 Stars")
        low_reviews = [r for r in reviews if r.get("starRating") in ("ONE", "TWO", "THREE")]
        if not low_reviews:
            st.info("No reviews with 3 stars or below in this period.")
        else:
            st.caption(f"{len(low_reviews)} low-rated review(s) in this period.")
            anthropic_key = st.secrets.get("anthropic", {}).get("api_key")
            if not anthropic_key:
                st.warning("Add `[anthropic]\\napi_key = 'sk-ant-...'` to `.streamlit/secrets.toml` to enable AI insights.")
            else:
                with st.spinner("Analysing low-rated reviews…"):
                    try:
                        st.write(_generate_insights(low_reviews, anthropic_key))
                    except Exception as exc:
                        _log.error("Insights generation failed: %s", exc)
                        if _debug(config):
                            st.error(f"Insights generation failed: {exc}")
                        else:
                            st.error("Could not generate insights. Please try again.")


def main() -> None:
    config = load_config()
    st.set_page_config(
        page_title=config["ui"]["app_title"],
        page_icon=config["ui"]["app_icon"],
        layout="wide",
    )

    # Must happen before ANYTHING else — including st.info/st.error calls —
    # so that Streamlit's own rerenders don't find the code again and
    # attempt a second exchange (codes are single-use → invalid_grant).
    params = st.query_params
    if "code" in params and "pending_code" not in st.session_state and "credentials" not in st.session_state:
        # Capture to locals BEFORE clearing — params is a live proxy, empty after clear()
        captured_code = params["code"]
        captured_state = params.get("state", "")
        st.query_params.clear()
        st.session_state["pending_code"] = captured_code
        st.session_state["pending_state"] = captured_state

    if "credentials" not in st.session_state and "pending_code" not in st.session_state:
        saved = _load_creds()
        if saved:
            st.session_state["credentials"] = saved
            _dbg("Restored credentials from cached file", config)

    if "pending_code" in st.session_state and "credentials" not in st.session_state:
        code = st.session_state.pop("pending_code")
        state = st.session_state.pop("pending_state", "")
        try:
            creds_json = exchange_code(code, state)
            st.session_state["credentials"] = creds_json
            _save_creds(creds_json)
            _dbg("Token exchange successful", config)
            st.rerun()
        except Exception as exc:
            # Store error in session_state so it survives any subsequent rerenders
            _log.error("Token exchange failed: %s", exc)
            st.session_state["_auth_error"] = str(exc)

    if "_auth_error" in st.session_state:
        st.error(f"Authentication failed: {st.session_state['_auth_error']}")
        if _debug(config):
            st.warning("Try clicking 'Sign in with Google' again. If the error persists, check that your redirect_uri in secrets.toml matches the GCP OAuth credentials exactly.")
        del st.session_state["_auth_error"]

    if "credentials" not in st.session_state:
        show_login(config)
    else:
        show_report(config)


if __name__ == "__main__":
    main()
