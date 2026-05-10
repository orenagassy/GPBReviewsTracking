import yaml
import streamlit as st
import plotly.graph_objects as go
import extra_streamlit_components as stx
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta

from auth import get_auth_url, exchange_code
from gbp_api import get_accounts, get_locations, get_reviews
from report import build_weekly_report

_CREDENTIALS_COOKIE = "gbp_creds"
_COOKIE_DAYS = 30


@st.cache_data
def load_config() -> dict:
    with open("config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _dbg(msg: str, config: dict) -> None:
    if config.get("debug_mode"):
        st.info(f"🔍 {msg}")


def show_login(config: dict) -> None:
    st.title(config["ui"]["app_title"])
    st.write(config["ui"]["signin_message"])
    st.link_button("Sign in with Google", get_auth_url(), type="primary")


def show_report(config: dict, cookie_manager) -> None:
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
            cookie_manager.delete(_CREDENTIALS_COOKIE)
            st.session_state.clear()
            # Prevent the cookie restore from immediately re-logging in
            # during this rerun while the async JS delete may not have landed yet.
            st.session_state["_signed_out"] = True
            st.rerun()

    if "accounts" not in st.session_state:
        with st.spinner("Loading accounts…"):
            try:
                accounts, creds_json = get_accounts(st.session_state["credentials"])
                st.session_state["credentials"] = creds_json
                st.session_state["accounts"] = accounts
            except Exception as exc:
                st.error(f"Failed to load accounts: {exc}")
                if config.get("debug_mode"):
                    st.exception(exc)
                return

    accounts = st.session_state["accounts"]
    if not accounts:
        st.warning("No Google Business Profile accounts found for this Google account.")
        return

    account_map = {a.get("accountName", a["name"]): a["name"] for a in accounts}
    selected_account_label = st.selectbox("Account", account_map)
    selected_account = account_map[selected_account_label]

    location_key = f"locations_{selected_account}"
    if location_key not in st.session_state:
        with st.spinner("Loading locations…"):
            try:
                locations, creds_json = get_locations(
                    st.session_state["credentials"], selected_account
                )
                st.session_state["credentials"] = creds_json
                st.session_state[location_key] = locations
            except Exception as exc:
                st.error(f"Failed to load locations: {exc}")
                if config.get("debug_mode"):
                    st.exception(exc)
                return

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

    # Capture auth code into local vars and clear the URL BEFORE any component
    # initialises. CookieManager triggers a Streamlit rerender; if ?code= is
    # still in the URL during that rerender it would be submitted to Google a
    # second time, causing invalid_grant (codes are single-use).
    # Must capture to local vars BEFORE st.query_params.clear() — the params
    # object is a live proxy and is empty after clear().
    params = st.query_params
    if "code" in params and "pending_code" not in st.session_state and "credentials" not in st.session_state:
        captured_code = params["code"]
        captured_state = params.get("state", "")
        st.query_params.clear()
        st.session_state["pending_code"] = captured_code
        st.session_state["pending_state"] = captured_state
        _dbg(f"Auth code captured from URL: {captured_code[:20]}…", config)

    cookie_manager = stx.CookieManager(key="gbp_cookie_mgr")

    # Restore credentials from persistent cookie when session is fresh.
    # Skipped when the user just signed out (_signed_out flag) to prevent
    # restoring before the async cookie-delete JS has landed in the browser.
    if (
        "credentials" not in st.session_state
        and "pending_code" not in st.session_state
        and not st.session_state.get("_signed_out")
    ):
        saved = cookie_manager.get(_CREDENTIALS_COOKIE)
        if saved:
            st.session_state["credentials"] = saved
            _dbg("Restored credentials from browser cookie", config)

    # Clear the sign-out guard after one render (by this point the browser
    # cookie delete has landed, so future page loads can restore normally).
    st.session_state.pop("_signed_out", None)

    # Exchange the pending code — popped so it can never be submitted twice.
    if "pending_code" in st.session_state and "credentials" not in st.session_state:
        code = st.session_state.pop("pending_code")
        state = st.session_state.pop("pending_state", "")
        _dbg(f"Exchanging auth code… state={state[:20]}…", config)
        try:
            creds_json = exchange_code(code, state)
            st.session_state["credentials"] = creds_json
            cookie_manager.set(
                _CREDENTIALS_COOKIE,
                creds_json,
                expires_at=datetime.now() + timedelta(days=_COOKIE_DAYS),
            )
            _dbg("Token exchange successful — credentials saved to session and cookie", config)
            st.rerun()
        except Exception as exc:
            st.error(f"Authentication failed: {exc}")
            if config.get("debug_mode"):
                st.exception(exc)
            # No rerun — keep the error visible

    if "credentials" not in st.session_state:
        show_login(config)
    else:
        show_report(config, cookie_manager)


if __name__ == "__main__":
    main()
