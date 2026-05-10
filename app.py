import yaml
import streamlit as st
from pathlib import Path
from datetime import date
from dateutil.relativedelta import relativedelta

from auth import get_auth_url, exchange_code
from gbp_api import get_accounts, get_locations, get_reviews
from report import build_weekly_report

# Credentials are cached here between page reloads.
# Gitignored — never committed.
_CREDS_FILE = Path(".streamlit") / "cached_creds.json"


@st.cache_data
def load_config() -> dict:
    with open("config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _dbg(msg: str, config: dict) -> None:
    if config.get("debug_mode"):
        st.info(f"🔍 {msg}")


def _save_creds(creds_json: str) -> None:
    try:
        if _CREDS_FILE.read_text(encoding="utf-8") == creds_json:
            return
    except OSError:
        pass
    _CREDS_FILE.write_text(creds_json, encoding="utf-8")


def _load_creds() -> str | None:
    try:
        return _CREDS_FILE.read_text(encoding="utf-8")
    except OSError:
        return None


def _clear_creds() -> None:
    _CREDS_FILE.unlink(missing_ok=True)


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
        if config.get("debug_mode"):
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
                st.session_state["accounts_error"] = f"Failed to load accounts: {exc}"
                st.rerun()

    accounts = st.session_state["accounts"]
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
                st.session_state[location_error_key] = f"Failed to load locations: {exc}"
                st.rerun()

    locations = st.session_state[location_key]
    if not locations:
        st.warning("No locations found for this account.")
        return

    location_map = {loc.get("title", loc["name"]): loc["name"] for loc in locations}
    selected_location_label = st.selectbox("Location", location_map)
    selected_location = location_map[selected_location_label]

    if st.button("Generate Report", type="primary"):
        end_date = date.today()
        start_date = end_date - relativedelta(months=months_back)

        with st.spinner("Fetching reviews…"):
            try:
                reviews, creds_json = get_reviews(
                    st.session_state["credentials"],
                    selected_location,
                    page_size=cfg_report["page_size"],
                )
                st.session_state["credentials"] = creds_json
                _save_creds(creds_json)
            except Exception as exc:
                st.error(f"Failed to fetch reviews: {exc}")
                if config.get("debug_mode"):
                    st.exception(exc)
                return

        _dbg(f"Fetched {len(reviews)} total reviews; filtering {start_date} → {end_date}", config)

        df = build_weekly_report(reviews, start_date, end_date)

        total_reviews = int(df["review_count"].sum())
        if total_reviews == 0:
            st.info("No reviews found in this date range.")
            return

        overall_avg = df.loc[df["review_count"] > 0, "avg_rating"].mean()

        k1, k2 = st.columns(2)
        k1.metric("Total Reviews", total_reviews)
        k2.metric("Overall Avg Rating", f"{overall_avg:.2f} ⭐")

        st.divider()

        c1, c2 = st.columns(2)

        with c1:
            st.subheader("Weekly Review Count")
            fig_bar = go.Figure(
                go.Bar(
                    x=df["week_start"],
                    y=df["review_count"],
                    marker_color=cfg_charts["bar_color"],
                )
            )
            fig_bar.update_layout(
                xaxis_title="Week (Monday)",
                yaxis_title="# Reviews",
                margin=dict(t=20, b=40),
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        with c2:
            st.subheader("Weekly Average Rating")
            fig_line = go.Figure(
                go.Scatter(
                    x=df["week_start"],
                    y=df["avg_rating"],
                    mode="lines+markers",
                    line=dict(color=cfg_charts["line_color"], width=2),
                    connectgaps=False,
                )
            )
            fig_line.update_layout(
                xaxis_title="Week (Monday)",
                yaxis_title="Avg Rating",
                yaxis=dict(range=[0.5, 5.5], tickvals=[1, 2, 3, 4, 5]),
                margin=dict(t=20, b=40),
            )
            st.plotly_chart(fig_line, use_container_width=True)

        st.subheader("Weekly Detail")
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "week_start": st.column_config.DateColumn("Week Starting", format="YYYY-MM-DD"),
                "review_count": st.column_config.NumberColumn("# Reviews"),
                "avg_rating": st.column_config.NumberColumn("Avg Rating", format="%.2f"),
            },
        )


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
        _dbg(f"Exchanging auth code: {code[:20]}…", config)
        try:
            creds_json = exchange_code(code, state)
            st.session_state["credentials"] = creds_json
            _save_creds(creds_json)
            _dbg("✅ Token exchange successful — you are now signed in", config)
            st.rerun()
        except Exception as exc:
            # Store error in session_state so it survives any subsequent rerenders
            st.session_state["_auth_error"] = str(exc)

    # Show persistent auth error (stored in session_state, not lost on rerender)
    if "_auth_error" in st.session_state:
        st.error(f"Authentication failed: {st.session_state['_auth_error']}")
        if config.get("debug_mode"):
            st.warning("Try clicking 'Sign in with Google' again. If the error persists, check that your redirect_uri in secrets.toml matches the GCP OAuth credentials exactly.")
        # Clear after display so re-login attempt starts fresh
        del st.session_state["_auth_error"]

    if "credentials" not in st.session_state:
        show_login(config)
    else:
        show_report(config)


if __name__ == "__main__":
    main()
