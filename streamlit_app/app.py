"""
Aura Health API — Streamlit Test Dashboard

A polished local testing UI for all Aura backend endpoints.
Configure API_URL via environment variable (defaults to http://localhost:8000).
"""

from __future__ import annotations

import os
from datetime import date

import httpx
import json
import time as _time
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

API_URL = os.environ.get("API_URL", "http://localhost:8000")
API_PREFIX = f"{API_URL}/api/v1"

# ---------------------------------------------------------------------------
# Design System
# ---------------------------------------------------------------------------

CHART_COLORS = {
    "mood": "#C4727F",
    "mood_fill": "rgba(196,114,127,0.15)",
    "energy": "#D4A574",
    "energy_fill": "rgba(212,165,116,0.15)",
    "sleep": "#5E4F6E",
    "sleep_fill": "rgba(94,79,110,0.15)",
    "symptom": "#D4645C",
    "symptom_fill": "rgba(212,100,92,0.15)",
}

NAV_ITEMS = [
    ("\U0001f512", "Auth"),
    ("\U0001f464", "Profile & Me"),
    ("\U0001f4ac", "Chat"),
    ("\U0001f338", "Cycle Tracker"),
    ("\U0001f4c8", "Health Log"),
    ("\U0001f4b3", "Subscriptions"),
    ("\U0001f3ab", "Tickets"),
    ("\U0001f338", "Wellness"),
    ("\U0001f511", "Admin"),
]

CUSTOM_CSS = """
:root {
    --aura-rose: #C4727F;
    --aura-rose-light: #E8A4AB;
    --aura-rose-dark: #A35763;
    --aura-peach: #F9E8E4;
    --aura-peach-dark: #EFD5CE;
    --aura-cream: #FFF8F6;
    --aura-plum: #3D3244;
    --aura-plum-light: #5E4F6E;
    --aura-gold: #D4A574;
    --aura-success: #6AAF7B;
    --aura-warning: #E2A642;
    --aura-error: #D4645C;
    --aura-info: #6A8CAF;
    --radius-sm: 6px;
    --radius-md: 10px;
    --radius-lg: 16px;
    --shadow-sm: 0 1px 3px rgba(61,50,68,0.08);
    --shadow-md: 0 4px 12px rgba(61,50,68,0.1);
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #3D3244 0%, #5E4F6E 100%) !important;
}
section[data-testid="stSidebar"] * {
    color: #FFF8F6 !important;
}
section[data-testid="stSidebar"] .stDivider {
    border-color: rgba(255,248,246,0.15) !important;
}
section[data-testid="stSidebar"] label[data-testid="stBaseButton-header"] {
    background: rgba(255,248,246,0.1) !important;
    border-color: rgba(255,248,246,0.2) !important;
}
section[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {
    color: #FFF8F6 !important;
    border-color: rgba(255,248,246,0.3) !important;
}
section[data-testid="stSidebar"] .stSuccess, section[data-testid="stSidebar"] .stInfo {
    background: rgba(255,248,246,0.08) !important;
    color: #FFF8F6 !important;
    border: none !important;
}
/* Sidebar radio items */
section[data-testid="stSidebar"] .stRadio > div {
    gap: 4px;
}
section[data-testid="stSidebar"] .stRadio label {
    padding: 6px 12px;
    border-radius: var(--radius-sm);
    transition: background 0.2s;
}
section[data-testid="stSidebar"] .stRadio label:hover {
    background: rgba(255,248,246,0.1);
}

/* Aura cards */
.aura-card {
    background: white;
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-sm);
    padding: 20px;
    margin-bottom: 16px;
    border: 1px solid var(--aura-peach-dark);
}
.aura-card-dark {
    background: var(--aura-plum);
    color: var(--aura-cream);
    border-radius: var(--radius-md);
    padding: 20px;
    margin-bottom: 16px;
}

/* Status badges */
.aura-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    text-transform: uppercase;
}
.badge-success { background: #e6f4ea; color: #1e7e34; }
.badge-error   { background: #fde8e8; color: #c0392b; }
.badge-warning { background: #fef5e7; color: #b7791f; }
.badge-info    { background: #e8f0fe; color: #2c5282; }
.badge-rose    { background: var(--aura-peach); color: var(--aura-rose-dark); }
.badge-gold    { background: #fef5e7; color: #975a16; }
.badge-plum    { background: #ede8f0; color: var(--aura-plum); }
.badge-open    { background: #e8f0fe; color: #2c5282; }
.badge-in-progress { background: #fef5e7; color: #b7791f; }
.badge-resolved { background: #e6f4ea; color: #1e7e34; }
.badge-closed  { background: #f0f0f0; color: #666; }
.badge-free    { background: #f0f0f0; color: #666; }
.badge-premium { background: linear-gradient(135deg,#f6e6b6,#d4a574); color: #5e3a1a; }
.badge-pending   { background: #fef5e7; color: #b7791f; }
.badge-processing { background: #e8f0fe; color: #2c5282; }
.badge-completed { background: #e6f4ea; color: #1e7e34; }
.badge-failed    { background: #fde8e8; color: #c0392b; }

/* Chat bubbles */
.aura-chat-user {
    background: var(--aura-rose);
    color: white;
    padding: 10px 16px;
    border-radius: 16px 16px 4px 16px;
    max-width: 75%;
    margin-left: auto;
    margin-bottom: 8px;
}
.aura-chat-assistant {
    background: var(--aura-peach);
    color: var(--aura-plum);
    padding: 10px 16px;
    border-radius: 16px 16px 16px 4px;
    max-width: 75%;
    margin-right: auto;
    margin-bottom: 8px;
}

/* Metric cards */
.aura-metric {
    text-align: center;
    padding: 16px;
    background: white;
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-sm);
    border: 1px solid var(--aura-peach-dark);
}
.aura-metric .metric-icon { font-size: 1.5rem; }
.aura-metric .metric-value { font-size: 1.8rem; font-weight: 700; color: var(--aura-plum); }
.aura-metric .metric-label { font-size: 0.85rem; color: var(--aura-plum-light); }

/* Ticket state machine flow */
.state-flow {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    padding: 12px 0;
}
.state-box {
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
}
.state-arrow { color: var(--aura-plum-light); font-size: 1.1rem; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: var(--radius-sm) var(--radius-sm) 0 0;
    padding: 8px 16px;
}
.stTabs [aria-selected="true"] {
    border-bottom: 2px solid var(--aura-rose) !important;
    color: var(--aura-rose-dark) !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-thumb { background: var(--aura-rose-light); border-radius: 3px; }
::-webkit-scrollbar-track { background: transparent; }

/* Spinner override */
.stSpinner > div { border-color: var(--aura-rose) transparent transparent transparent !important; }
"""


def _inject_css() -> None:
    st.markdown(f"<style>{CUSTOM_CSS}</style>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _headers() -> dict[str, str]:
    token = st.session_state.get("access_token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _api_call(method: str, path: str, *, json_data=None, params=None) -> httpx.Response:
    url = f"{API_PREFIX}{path}"
    return httpx.request(method, url, json=json_data, params=params, headers=_headers(), timeout=30)


def _status_badge_html(code: int) -> str:
    if 200 <= code < 300:
        cls = "badge-success"
    elif 400 <= code < 500:
        cls = "badge-warning"
    else:
        cls = "badge-error"
    return f'<span class="aura-badge {cls}">{code}</span>'


def _badge_html(text: str, cls: str = "badge-info") -> str:
    return f'<span class="aura-badge {cls}">{text}</span>'


def _ticket_status_badge(status: str) -> str:
    return _badge_html(status, f"badge-{status.replace(' ', '-')}")


def _tier_badge(tier: str) -> str:
    return _badge_html(tier.upper(), "badge-premium" if tier == "premium" else "badge-free")


def _analysis_status_badge(status: str) -> str:
    return _badge_html(status, f"badge-{status}")


def _display_response_rich(resp: httpx.Response, *, title: str = "Response") -> None:
    """Display an API response with status badge, rich content, and expandable raw JSON."""
    st.markdown(_status_badge_html(resp.status_code), unsafe_allow_html=True)

    if 200 <= resp.status_code < 300:
        try:
            data = resp.json()
        except Exception:
            st.code(resp.text)
            return

        if isinstance(data, list) and data:
            df = pd.DataFrame(data)
            # Truncate long string columns for readability
            for col in df.columns:
                if df[col].dtype == object:
                    df[col] = df[col].astype(str).str.slice(0, 60)
            st.dataframe(df, hide_index=True, width="stretch")
            with st.expander("Raw JSON"):
                st.json(resp.json())
        elif isinstance(data, dict):
            # Show key-value pairs in a card
            pairs = []
            skip = {"user_id", "id"}
            for k, v in data.items():
                if k in skip:
                    continue
                if isinstance(v, list) and v and isinstance(v[0], str):
                    pairs.append((k, " ".join(_badge_html(item, "badge-rose") for item in v)))
                elif isinstance(v, dict):
                    continue  # skip nested dicts from display
                else:
                    pairs.append((k, str(v)))

            if pairs:
                cols = st.columns(min(len(pairs), 3))
                for i, (k, v) in enumerate(pairs):
                    with cols[i % len(cols)]:
                        st.markdown(
                            f'<div class="aura-metric"><div class="metric-value">{v}</div>'
                            f'<div class="metric-label">{k}</div></div>',
                            unsafe_allow_html=True,
                        )

            with st.expander("Raw JSON"):
                st.json(resp.json())
    elif resp.status_code == 422:
        st.error("Validation Error")
        try:
            data = resp.json()
            if "errors" in data:
                for err in data["errors"]:
                    st.warning(f"`{err.get('field', '?')}`: {err.get('message', '?')}")
            else:
                st.json(data)
        except Exception:
            st.code(resp.text)
    else:
        try:
            data = resp.json()
            detail = data.get("detail", {})
            if isinstance(detail, dict):
                msg = detail.get("message", detail.get("error", ""))
                if msg:
                    st.error(msg)
                if detail.get("allowed_transitions"):
                    st.caption(f"Allowed: {', '.join(detail['allowed_transitions'])}")
            elif isinstance(detail, str):
                st.error(detail)
            with st.expander("Raw JSON"):
                st.json(data)
        except Exception:
            st.code(resp.text)


def _display_response(resp: httpx.Response) -> None:
    """Backward-compatible wrapper."""
    _display_response_rich(resp)


def _metric_card(icon: str, value: str, label: str) -> None:
    st.markdown(
        f'<div class="aura-metric"><div class="metric-icon">{icon}</div>'
        f'<div class="metric-value">{value}</div>'
        f'<div class="metric-label">{label}</div></div>',
        unsafe_allow_html=True,
    )


def _brand_chart_layout(title: str, y_range: list | None = None) -> go.Layout:
    layout = go.Layout(
        title=dict(text=title, font=dict(size=16, color="#3D3244")),
        paper_bgcolor="#FFF8F6",
        plot_bgcolor="#FFF8F6",
        font=dict(family="sans-serif", color="#3D3244"),
        margin=dict(l=50, r=20, t=50, b=40),
        xaxis=dict(gridcolor="#EFD5CE"),
        yaxis=dict(gridcolor="#EFD5CE"),
        hoverlabel=dict(bgcolor="#3D3244", font=dict(color="white")),
    )
    if y_range:
        layout.yaxis.range = y_range
    return layout


def _ensure_auth() -> bool:
    if not st.session_state.get("access_token"):
        st.warning("Please log in first (see Auth page).")
        return False
    return True


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            '<div style="text-align:center;padding:8px 0">'
            '<span style="font-size:2rem">\U0001f338</span><br>'
            '<span style="font-size:1.4rem;font-weight:700;color:#FFF8F6">Aura Health</span><br>'
            '<span style="font-size:0.8rem;opacity:0.7">Test Dashboard</span></div>',
            unsafe_allow_html=True,
        )
        st.divider()

        # Auth status
        if st.session_state.get("access_token"):
            email = st.session_state.get("user_email", "unknown")
            st.markdown(
                f'<span style="color:#6AAF7B">\u25cf</span> <b>{email}</b>',
                unsafe_allow_html=True,
            )
            if st.button("Sign Out", width="stretch"):
                _do_signout()
        else:
            st.markdown('<span style="color:#999">\u25cb</span> Not authenticated', unsafe_allow_html=True)

        st.divider()

        # Navigation with icons
        labels = [f"{icon} {name}" for icon, name in NAV_ITEMS]
        page = st.radio("Navigate", labels, label_visibility="collapsed")
        # Strip icon prefix to get the key
        st.session_state["page"] = page.split(" ", 1)[1] if " " in page else page

        st.divider()
        st.caption(f"\U0001f310 API: `{API_URL}`")


def _do_signout() -> None:
    _api_call("POST", "/auth/signout")
    for key in ["access_token", "refresh_token", "user_email"]:
        st.session_state.pop(key, None)
    st.sidebar.success("Signed out!")


# ---------------------------------------------------------------------------
# Auth Page
# ---------------------------------------------------------------------------


def _render_auth() -> None:
    st.header("\U0001f512 Authentication")

    tab_reg, tab_login, tab_refresh = st.tabs(["Register", "Login", "Refresh Token"])

    with tab_reg:
        st.markdown('<div class="aura-card">', unsafe_allow_html=True)
        st.subheader("Register New User")
        with st.form("register_form"):
            reg_email = st.text_input("\U0001f4e7 Email", key="reg_email")
            reg_password = st.text_input("\U0001f510 Password", type="password", key="reg_password",
                                          help="Minimum 8 characters")
            reg_name = st.text_input("\U0001f464 Full Name", key="reg_name")
            reg_submitted = st.form_submit_button("\u2795 Register")

        if reg_submitted:
            if not reg_email or not reg_password or not reg_name:
                st.warning("All fields are required.")
            else:
                resp = _api_call("POST", "/auth/register", json_data={
                    "email": reg_email, "password": reg_password, "full_name": reg_name,
                })
                if 200 <= resp.status_code < 300:
                    data = resp.json()
                    st.success("Account created!")
                    col1, col2 = st.columns(2)
                    col1.markdown(f'<div class="aura-metric"><div class="metric-value">{data.get("email","")}</div>'
                                  f'<div class="metric-label">Email</div></div>', unsafe_allow_html=True)
                    col2.markdown(f'<div class="aura-metric"><div class="metric-value">{str(data.get("user_id",""))[:8]}...</div>'
                                  f'<div class="metric-label">User ID</div></div>', unsafe_allow_html=True)
                    with st.expander("Raw JSON"):
                        st.json(data)
                else:
                    _display_response_rich(resp)
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_login:
        st.markdown('<div class="aura-card">', unsafe_allow_html=True)
        st.subheader("Sign In")
        with st.form("login_form"):
            login_email = st.text_input("\U0001f4e7 Email", key="login_email")
            login_password = st.text_input("\U0001f510 Password", type="password", key="login_password")
            login_submitted = st.form_submit_button("\U0001f511 Sign In")

        if login_submitted:
            if not login_email or not login_password:
                st.warning("Email and password are required.")
            else:
                resp = _api_call("POST", "/auth/token", json_data={
                    "email": login_email, "password": login_password,
                })
                if resp.status_code == 400:
                    try:
                        detail = resp.json().get("detail", "")
                        if "email_not_confirmed" in str(detail):
                            st.error("\u26a0 Email not confirmed yet. Check your inbox or disable 'Confirm email' "
                                     "in Supabase Dashboard > Authentication > Providers.")
                        else:
                            _display_response_rich(resp)
                    except Exception:
                        _display_response_rich(resp)
                elif 200 <= resp.status_code < 300:
                    data = resp.json()
                    st.session_state["access_token"] = data["access_token"]
                    st.session_state["refresh_token"] = data["refresh_token"]
                    st.session_state["user_email"] = login_email
                    st.success(f"\u2705 Logged in as {login_email}")
                    st.markdown(_badge_html("Session Active", "badge-success"), unsafe_allow_html=True)
                    with st.expander("Token Details"):
                        st.text_input("Access Token", value=data["access_token"], disabled=True, key="login_access_token")
                        st.text_input("Refresh Token", value=data["refresh_token"], disabled=True, key="login_refresh_token")
                else:
                    _display_response_rich(resp)
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_refresh:
        st.markdown('<div class="aura-card">', unsafe_allow_html=True)
        st.subheader("Refresh Token")
        refresh_token = st.text_input("Refresh Token",
                                      value=st.session_state.get("refresh_token", ""),
                                      key="refresh_input")
        if st.button("\U0001f504 Refresh", width="stretch"):
            if not refresh_token:
                st.warning("No refresh token available.")
            else:
                resp = _api_call("POST", "/auth/refresh", json_data={"refresh_token": refresh_token})
                if 200 <= resp.status_code < 300:
                    data = resp.json()
                    st.session_state["access_token"] = data["access_token"]
                    st.session_state["refresh_token"] = data["refresh_token"]
                    st.success("\u2705 Token refreshed!")
                    with st.expander("New Tokens"):
                        st.json(data)
                else:
                    _display_response_rich(resp)
        st.markdown('</div>', unsafe_allow_html=True)

    st.divider()
    st.subheader("Session Info")
    if st.session_state.get("access_token"):
        st.markdown(_badge_html("Connected", "badge-success"), unsafe_allow_html=True)
        with st.expander("View Tokens"):
            st.text_input("Access Token", value=st.session_state["access_token"], disabled=True, key="session_access_token")
            st.text_input("Refresh Token", value=st.session_state.get("refresh_token", ""), disabled=True, key="session_refresh_token")
    else:
        st.info("No active session. Log in above.")


# ---------------------------------------------------------------------------
# Profile & Me Page
# ---------------------------------------------------------------------------


def _render_profile() -> None:
    st.header("\U0001f464 Profile & Me")
    if not _ensure_auth():
        return

    tab_me, tab_upsert = st.tabs(["Get Me", "Upsert Profile"])

    with tab_me:
        if st.button("\U0001f50d Fetch /me", width="stretch"):
            resp = _api_call("GET", "/me")
            if 200 <= resp.status_code < 300:
                data = resp.json()
                profile = data.get("profile") or {}
                subscription = data.get("subscription", {})

                st.markdown('<div class="aura-card">', unsafe_allow_html=True)
                st.subheader("\U0001f464 Profile")
                col1, col2, col3 = st.columns(3)
                col1.markdown(
                    f'<div class="aura-metric"><div class="metric-value">{profile.get("full_name","N/A")}</div>'
                    f'<div class="metric-label">Name</div></div>', unsafe_allow_html=True)
                col2.markdown(
                    f'<div class="aura-metric"><div class="metric-value">{profile.get("language","N/A")}</div>'
                    f'<div class="metric-label">Language</div></div>', unsafe_allow_html=True)
                col3.markdown(
                    f'<div class="aura-metric"><div class="metric-value">{profile.get("country","N/A")}</div>'
                    f'<div class="metric-label">Country</div></div>', unsafe_allow_html=True)

                goals = profile.get("health_goals", [])
                conditions = profile.get("conditions", [])
                if goals:
                    st.markdown("**Health Goals:** " + " ".join(_badge_html(g, "badge-rose") for g in goals),
                                unsafe_allow_html=True)
                if conditions:
                    st.markdown("**Conditions:** " + " ".join(_badge_html(c, "badge-warning") for c in conditions),
                                unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

                st.markdown('<div class="aura-card">', unsafe_allow_html=True)
                st.subheader("\U0001f4b3 Subscription")
                tier = subscription.get("tier", "free")
                sub_status = subscription.get("status", "active")
                col1, col2 = st.columns(2)
                col1.markdown(_tier_badge(tier), unsafe_allow_html=True)
                col2.markdown(_badge_html(sub_status.upper(), "badge-success"), unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

                with st.expander("Raw JSON"):
                    st.json(data)
            else:
                _display_response_rich(resp)

    with tab_upsert:
        st.markdown('<div class="aura-card">', unsafe_allow_html=True)
        st.subheader("Create or Update Profile")
        with st.form("profile_form"):
            p_name = st.text_input("\U0001f464 Full Name")
            p_lang = st.selectbox("\U0001f310 Language", ["ar", "en"])
            p_country = st.text_input("\U0001f30d Country (2-letter code)", max_chars=2)
            p_dob = st.date_input("\U0001f382 Date of Birth", value=None, format="YYYY-MM-DD")
            p_goals = st.text_input("\U0001f3af Health Goals (comma-separated)")
            p_conditions = st.text_input("\U0001f3e5 Conditions (comma-separated)")
            p_submitted = st.form_submit_button("\u270f Upsert Profile")

        if p_submitted:
            data: dict = {}
            if p_name:
                data["full_name"] = p_name
            if p_lang:
                data["language"] = p_lang
            if p_country:
                data["country"] = p_country
            if p_dob:
                data["date_of_birth"] = str(p_dob)
            if p_goals:
                data["health_goals"] = [g.strip() for g in p_goals.split(",")]
            if p_conditions:
                data["conditions"] = [c.strip() for c in p_conditions.split(",")]

            resp = _api_call("POST", "/auth/profile", json_data=data)
            if 200 <= resp.status_code < 300:
                st.success("\u2705 Profile saved!")
                with st.expander("Raw JSON"):
                    st.json(resp.json())
            else:
                _display_response_rich(resp)
        st.markdown('</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Chat Page
# ---------------------------------------------------------------------------


def _render_chat() -> None:
    st.header("\U0001f4ac Chat")
    if not _ensure_auth():
        return

    tab_send, tab_convos = st.tabs(["Send Message", "Conversations"])

    with tab_send:
        st.markdown('<div class="aura-card">', unsafe_allow_html=True)

        # --- Conversation selector ---
        convos = []
        try:
            resp = _api_call("GET", "/chat/conversations")
            if 200 <= resp.status_code < 300:
                convos = resp.json()
        except Exception:
            pass

        convo_options = ["\U0001f195 New Conversation"] + [
            f"{c.get('title', 'Untitled')}" for c in convos
        ]
        selected_convo = st.selectbox("Conversation", convo_options, index=0)
        convo_id = None if "New" in selected_convo else convos[convo_options.index(selected_convo) - 1]["id"] \
            if convos and selected_convo != convo_options[0] else None

        chat_lang = st.selectbox("\U0001f310 Language", ["en", "ar"], index=0)

        # --- File upload ---
        st.markdown("**\U0001f4ce Attach a file (image or PDF)**")
        uploaded_chat_file = st.file_uploader(
            "Choose an image or PDF",
            type=["jpg", "jpeg", "png", "webp", "heic", "pdf"],
            help="Attach an image or PDF to include with your message. "
                 "It will be uploaded to storage and analysed if applicable.",
            key="chat_file_uploader",
        )

        if uploaded_chat_file is not None:
            if uploaded_chat_file.type and uploaded_chat_file.type.startswith("image/"):
                st.image(uploaded_chat_file, caption=uploaded_chat_file.name, width="stretch")
            else:
                st.info(f"\U0001f4c4 {uploaded_chat_file.name} ({uploaded_chat_file.size:,} bytes)")

        # --- Message input ---
        chat_msg = st.text_area("\u270f Message", height=100)

        if st.button("\U0001f4e4 Send", width="stretch"):
            if not chat_msg.strip():
                st.warning("Enter a message.")
            else:
                file_path_to_send = None
                file_type_to_send = None

                # Step 1: Upload file if attached
                if uploaded_chat_file is not None:
                    with st.spinner("\U0001f4e4 Uploading file..."):
                        content_type_upload = uploaded_chat_file.type or "image/jpeg"
                        # Get signed upload URL
                        resp_url = _api_call("POST", "/analysis/upload-url", json_data={
                            "file_name": uploaded_chat_file.name,
                            "content_type": content_type_upload,
                            "analysis_type": "skin" if content_type_upload.startswith("image/") else "report",
                        })
                        if 200 <= resp_url.status_code < 300:
                            url_data = resp_url.json()
                            upload_url = url_data["upload_url"]
                            file_path_to_send = url_data["file_path"]
                            file_type_to_send = content_type_upload

                            # Upload the file bytes to the signed URL
                            uploaded_chat_file.seek(0)
                            file_bytes = uploaded_chat_file.read()
                            put_resp = httpx.put(
                                upload_url,
                                content=file_bytes,
                                headers={"Content-Type": content_type_upload},
                                timeout=60,
                            )
                            if not (200 <= put_resp.status_code < 300):
                                st.error(f"File upload to storage failed: {put_resp.status_code}")
                                st.code(put_resp.text[:500])
                                file_path_to_send = None
                        else:
                            st.error("Failed to get upload URL for attached file.")
                            _display_response_rich(resp_url)
                            file_path_to_send = None

                # Step 2: Send chat message (with file_path/file_type if attached)
                payload: dict = {"content": chat_msg, "language": chat_lang}
                if convo_id:
                    payload["conversation_id"] = convo_id
                if file_path_to_send:
                    payload["file_path"] = file_path_to_send
                    payload["file_type"] = file_type_to_send

                url = f"{API_PREFIX}/chat/message"
                headers = _headers()
                headers["Accept"] = "text/event-stream"

                response_text = ""
                analysis_meta_info = None
                error_info = None
                with st.spinner("\U0001f4ac Streaming response..."):
                    with httpx.stream("POST", url, json=payload, headers=headers, timeout=120) as stream:
                        for line in stream.iter_lines():
                            if not line.startswith("data: "):
                                continue
                            raw = line[6:]
                            if raw.strip() == "[DONE]":
                                break
                            try:
                                event = json.loads(raw)
                            except json.JSONDecodeError:
                                # Fallback: treat as plain text content
                                response_text += raw
                                continue

                            event_type = event.get("type", "")
                            if event_type == "content":
                                response_text += event.get("text", "")
                            elif event_type == "analysis_meta":
                                analysis_meta_info = event
                            elif event_type == "quota_error":
                                error_info = ("quota", event.get("message", "Quota exceeded"))
                            elif event_type == "analysis_error":
                                error_info = ("analysis", event.get("message", "Analysis error"))

                # Show user bubble
                if file_path_to_send:
                    file_label = "\U0001f4ce " + (uploaded_chat_file.name if uploaded_chat_file else "file")
                    st.markdown(
                        f'<div class="aura-chat-user">{chat_msg}<br><small>{file_label}</small></div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(f'<div class="aura-chat-user">{chat_msg}</div>', unsafe_allow_html=True)

                # Show assistant bubble and errors
                if error_info and error_info[0] == "quota":
                    st.error(f"\u26a0 {error_info[1]}")
                elif error_info and error_info[0] == "analysis":
                    st.warning(f"\u26a0 Analysis error: {error_info[1]}")

                if response_text:
                    st.markdown(f'<div class="aura-chat-assistant">{response_text}</div>', unsafe_allow_html=True)

                # Step 3: Fetch and display analysis results if meta was received
                if analysis_meta_info:
                    analysis_id = analysis_meta_info.get("analysis_id", "")
                    analysis_type = analysis_meta_info.get("analysis_type", "unknown")
                    st.markdown(
                        _badge_html(f"Analysis: {analysis_type}", "badge-rose") +
                        " " + _badge_html(f"ID: {analysis_id[:8]}...", "badge-info"),
                        unsafe_allow_html=True,
                    )

                    # Try to fetch analysis results
                    fetch_convo_id = convo_id
                    if not fetch_convo_id:
                        try:
                            refresh_resp = _api_call("GET", "/chat/conversations")
                            if 200 <= refresh_resp.status_code < 300:
                                latest = refresh_resp.json()
                                if latest:
                                    fetch_convo_id = latest[0].get("id")
                        except Exception:
                            pass

                    if fetch_convo_id:
                        with st.spinner("\U0001f52c Fetching analysis results..."):
                            # Give the backend a moment to finish processing
                            _time.sleep(2)
                            analysis_resp = _api_call(
                                "GET", f"/chat/conversations/{fetch_convo_id}/analysis"
                            )
                            if 200 <= analysis_resp.status_code < 300:
                                analysis_data = analysis_resp.json()
                                result = analysis_data.get("result", {})
                                status = analysis_data.get("status", "unknown")
                                st.markdown(_analysis_status_badge(status), unsafe_allow_html=True)

                                if result and isinstance(result, dict):
                                    with st.expander("\U0001f52c Analysis Results", expanded=True):
                                        for k, v in result.items():
                                            if isinstance(v, list):
                                                st.markdown(f"**{k.replace('_', ' ').title()}:**")
                                                for item in v:
                                                    if isinstance(item, dict):
                                                        for ik, iv in item.items():
                                                            st.markdown(f"- **{ik}:** {iv}")
                                                    else:
                                                        st.markdown(f"- {item}")
                                            elif isinstance(v, dict):
                                                st.markdown(f"**{k.replace('_', ' ').title()}:**")
                                                for ik, iv in v.items():
                                                    st.markdown(f"- **{ik}:** {iv}")
                                            else:
                                                st.markdown(f"**{k.replace('_', ' ').title()}:** {v}")
                                elif status in ("pending", "processing"):
                                    st.info("Analysis is still processing. Check the Analysis tab for results later.")
                            elif analysis_resp.status_code == 404:
                                st.info("Analysis results not yet available. Check the Analysis tab later.")
                elif not error_info and not response_text:
                    st.warning("No response received from the server.")
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_convos:
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("\U0001f504 Refresh", width="stretch"):
                resp = _api_call("GET", "/chat/conversations")
                if 200 <= resp.status_code < 300:
                    st.session_state["chat_convos"] = resp.json()

        convos = st.session_state.get("chat_convos", [])
        if convos:
            for c in convos:
                title = c.get("title", "Untitled")
                lang = c.get("language", "?")
                msg_count = c.get("message_count", 0)
                with st.expander(f"\U0001f4ac {title}"):
                    st.markdown(
                        _badge_html(lang.upper(), "badge-info") + " " +
                        _badge_html(f"{msg_count} msgs", "badge-plum"),
                        unsafe_allow_html=True,
                    )
                    st.caption(f"ID: {c['id'][:8]}... | Created: {c.get('created_at', '?')[:10]}")

                    col_v, col_d = st.columns(2)
                    with col_v:
                        if st.button("\U0001f441 View", key=f"view_{c['id']}"):
                            resp = _api_call("GET", f"/chat/conversations/{c['id']}/messages")
                            if 200 <= resp.status_code < 300:
                                msgs = resp.json()
                                for m in msgs:
                                    role = m.get("role", "unknown")
                                    content = m.get("content", "")
                                    cls = "aura-chat-user" if role == "user" else "aura-chat-assistant"
                                    file_info = ""
                                    if m.get("file_path"):
                                        file_info = f'<br><small>\U0001f4ce {m["file_path"]}</small>'
                                    st.markdown(f'<div class="{cls}">{content}{file_info}</div>', unsafe_allow_html=True)
                            else:
                                _display_response_rich(resp)
                    with col_d:
                        if st.button("\U0001f5d1 Delete", key=f"del_{c['id']}"):
                            resp = _api_call("DELETE", f"/chat/conversations/{c['id']}")
                            if 200 <= resp.status_code < 300:
                                st.success("Deleted!")
                                st.session_state.pop("chat_convos", None)
                            else:
                                _display_response_rich(resp)
        else:
            st.info("No conversations yet. Click Refresh to load.")



# ---------------------------------------------------------------------------
# Health Log Page
# ---------------------------------------------------------------------------


def _render_health_log() -> None:
    st.header("\U0001f4c8 Health Log")
    if not _ensure_auth():
        return

    tab_upsert, tab_list, tab_summary, tab_date = st.tabs(
        ["Log Entry", "List Logs", "Summary & Charts", "Get / Delete by Date"]
    )

    with tab_upsert:
        st.markdown('<div class="aura-card">', unsafe_allow_html=True)
        st.subheader("Create / Update Log Entry")
        with st.form("health_log_form"):
            hl_date = st.date_input("\U0001f4c5 Date", value=date.today())
            hl_mood = st.slider("\U0001f60a Mood (1-10)", 1, 10, value=5)
            hl_energy = st.slider("\U0001f50b Energy (1-10)", 1, 10, value=5)
            hl_sleep = st.slider("\U0001f319 Sleep Hours (0-24)", 0.0, 24.0, value=7.0, step=0.5)
            hl_water = st.number_input("\U0001f4a7 Water (ml)", min_value=0, value=0)
            hl_exercise = st.number_input("\U0001f3cb Exercise (minutes)", min_value=0, value=0)
            hl_symptoms = st.text_input("\U0001f3e5 Symptoms (comma-separated)")
            hl_notes = st.text_area("\U0001f4dd Notes", height=80)
            hl_submitted = st.form_submit_button("\u2705 Save Log")

        if hl_submitted:
            data: dict = {"log_date": str(hl_date), "mood": hl_mood, "energy": hl_energy}
            if hl_sleep:
                data["sleep_hours"] = hl_sleep
            if hl_water:
                data["water_ml"] = hl_water
            if hl_exercise:
                data["exercise_minutes"] = hl_exercise
            if hl_symptoms.strip():
                data["symptoms"] = [s.strip() for s in hl_symptoms.split(",")]
            if hl_notes.strip():
                data["notes"] = hl_notes

            resp = _api_call("POST", "/health-log", json_data=data)
            if 200 <= resp.status_code < 300:
                st.success("\u2705 Log saved!")
                with st.expander("Raw JSON"):
                    st.json(resp.json())
            else:
                _display_response_rich(resp)
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_list:
        st.subheader("Recent Logs")
        hl_days = st.number_input("\U0001f4c5 Days", min_value=1, max_value=365, value=30, key="hl_days")
        if st.button("\U0001f4da Load Logs", width="stretch"):
            resp = _api_call("GET", "/health-log", params={"days": hl_days})
            _display_response_rich(resp)

    with tab_summary:
        st.subheader("\U0001f4ca Health Summary & Charts")
        summary_days = st.slider("\U0001f4c5 Days", min_value=7, max_value=90, value=30, key="summary_days")
        if st.button("\U0001f504 Load Summary", width="stretch"):
            resp = _api_call("GET", "/health-log/summary", params={"days": summary_days})
            if 200 <= resp.status_code < 300:
                data = resp.json()

                # Metric cards
                col1, col2, col3 = st.columns(3)
                col1.markdown(
                    f'<div class="aura-metric"><div class="metric-icon">\U0001f4c5</div>'
                    f'<div class="metric-value">{data.get("entry_count",0)}</div>'
                    f'<div class="metric-label">Days Tracked</div></div>', unsafe_allow_html=True)
                col2.markdown(
                    f'<div class="aura-metric"><div class="metric-icon">\U0001f3cb</div>'
                    f'<div class="metric-value">{data.get("exercise_total_minutes",0)}</div>'
                    f'<div class="metric-label">Total Exercise (min)</div></div>', unsafe_allow_html=True)
                col3.markdown(
                    f'<div class="aura-metric"><div class="metric-icon">\U0001f4a7</div>'
                    f'<div class="metric-value">{round(data.get("water_avg_ml",0))}</div>'
                    f'<div class="metric-label">Avg Water (ml)</div></div>', unsafe_allow_html=True)

                # Mood trend
                mood_trend = data.get("mood_trend", [])
                if mood_trend:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=[d["date"] for d in mood_trend], y=[d["value"] for d in mood_trend],
                        mode="lines+markers", name="Mood",
                        line=dict(color=CHART_COLORS["mood"], width=2),
                        fill="tozeroy", fillcolor=CHART_COLORS["mood_fill"],
                    ))
                    fig.update_layout(_brand_chart_layout("Mood Trend", [1, 10]))
                    st.plotly_chart(fig, width="stretch")

                # Energy trend
                energy_trend = data.get("energy_trend", [])
                if energy_trend:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=[d["date"] for d in energy_trend], y=[d["value"] for d in energy_trend],
                        mode="lines+markers", name="Energy",
                        line=dict(color=CHART_COLORS["energy"], width=2),
                        fill="tozeroy", fillcolor=CHART_COLORS["energy_fill"],
                    ))
                    fig.update_layout(_brand_chart_layout("Energy Trend", [1, 10]))
                    st.plotly_chart(fig, width="stretch")

                # Mood + Energy overlay
                if mood_trend and energy_trend:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=[d["date"] for d in mood_trend], y=[d["value"] for d in mood_trend],
                        mode="lines+markers", name="Mood",
                        line=dict(color=CHART_COLORS["mood"], width=2),
                    ))
                    fig.add_trace(go.Scatter(
                        x=[d["date"] for d in energy_trend], y=[d["value"] for d in energy_trend],
                        mode="lines+markers", name="Energy",
                        line=dict(color=CHART_COLORS["energy"], width=2, dash="dot"),
                    ))
                    fig.update_layout(_brand_chart_layout("Mood & Energy", [1, 10]))
                    st.plotly_chart(fig, width="stretch")

                # Sleep trend
                sleep_trend = data.get("sleep_trend", [])
                if sleep_trend:
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        x=[d["date"] for d in sleep_trend], y=[d["value"] for d in sleep_trend],
                        name="Sleep Hours", marker_color=CHART_COLORS["sleep"],
                        marker_line_width=0,
                    ))
                    fig.update_layout(_brand_chart_layout("Sleep Trend", [0, 24]))
                    st.plotly_chart(fig, width="stretch")

                # Symptom frequency
                symptoms = data.get("symptom_frequency", [])
                if symptoms:
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        x=[s["symptom"] for s in symptoms], y=[s["count"] for s in symptoms],
                        marker_color=CHART_COLORS["symptom"], marker_line_width=0,
                    ))
                    fig.update_layout(_brand_chart_layout("Symptom Frequency"))
                    st.plotly_chart(fig, width="stretch")
            else:
                _display_response_rich(resp)

    with tab_date:
        st.markdown('<div class="aura-card">', unsafe_allow_html=True)
        st.subheader("Get / Delete by Date")
        lookup_date = st.date_input("\U0001f4c5 Date", value=date.today(), key="hl_lookup_date")
        col_get, col_del = st.columns(2)
        with col_get:
            if st.button("\U0001f50d Get Log", width="stretch"):
                resp = _api_call("GET", f"/health-log/{lookup_date}")
                _display_response_rich(resp)
        with col_del:
            if st.button("\U0001f5d1 Delete Log", width="stretch"):
                resp = _api_call("DELETE", f"/health-log/{lookup_date}")
                _display_response_rich(resp)
        st.markdown('</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Subscriptions Page
# ---------------------------------------------------------------------------


def _render_subscriptions() -> None:
    st.header("\U0001f4b3 Subscriptions")
    if not _ensure_auth():
        return

    tab_status, tab_checkout = st.tabs(["Status", "Checkout"])

    with tab_status:
        st.markdown('<div class="aura-card">', unsafe_allow_html=True)
        st.subheader("Subscription Status")
        if st.button("\U0001f50d Check Status", width="stretch"):
            resp = _api_call("GET", "/subscribe/status")
            if 200 <= resp.status_code < 300:
                data = resp.json()
                tier = data.get("tier", "free")
                sub_status = data.get("status", "active")
                col1, col2 = st.columns(2)
                col1.markdown(_tier_badge(tier), unsafe_allow_html=True)
                col2.markdown(_badge_html(sub_status.upper(), "badge-success"), unsafe_allow_html=True)
                if data.get("current_period_end"):
                    st.caption(f"Period ends: {data['current_period_end'][:10]}")
                with st.expander("Raw JSON"):
                    st.json(data)
            else:
                _display_response_rich(resp)
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_checkout:
        st.markdown('<div class="aura-card">', unsafe_allow_html=True)
        st.subheader("\u2728 Upgrade to Premium")
        st.info("This will create a Stripe Checkout session and return a redirect URL.")
        if st.button("\U0001f680 Start Premium Checkout", width="stretch"):
            resp = _api_call("POST", "/subscribe/checkout")
            if 200 <= resp.status_code < 300:
                data = resp.json()
                url = data.get("url", data.get("checkout_url", ""))
                if url:
                    st.success("Checkout session created!")
                    st.markdown(f'[**\U0001f517 Open Checkout Page**]({url})')
                else:
                    st.json(data)
            else:
                _display_response_rich(resp)
        st.markdown('</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Tickets Page
# ---------------------------------------------------------------------------


VALID_TRANSITIONS = {
    "open": {"in_progress"},
    "in_progress": {"resolved", "closed"},
    "resolved": {"closed"},
    "closed": set(),
}

STATE_COLORS = {
    "open": "#6A8CAF",
    "in_progress": "#E2A642",
    "resolved": "#6AAF7B",
    "closed": "#999",
}


def _render_tickets() -> None:
    st.header("\U0001f3ab Tickets")
    if not _ensure_auth():
        return

    tab_create, tab_list, tab_detail, tab_transition = st.tabs(
        ["Create", "List", "Detail", "Transition Status"]
    )

    with tab_create:
        st.markdown('<div class="aura-card">', unsafe_allow_html=True)
        st.subheader("Create Ticket")
        with st.form("ticket_create_form"):
            t_subject = st.text_input("\u270f Subject", max_chars=200)
            t_desc = st.text_area("\U0001f4dd Description", height=120, max_chars=5000)
            t_priority = st.selectbox("\U0001f534 Priority", ["low", "medium", "high"])
            t_submitted = st.form_submit_button("\u2795 Create Ticket")

        if t_submitted:
            if not t_subject or not t_desc:
                st.warning("Subject and description are required.")
            else:
                resp = _api_call("POST", "/tickets", json_data={
                    "subject": t_subject, "description": t_desc, "priority": t_priority,
                })
                if 200 <= resp.status_code < 300:
                    data = resp.json()
                    st.success("\u2705 Ticket created!")
                    st.markdown(f'**ID:** `{data.get("id","")}`')
                    st.markdown(_ticket_status_badge(data.get("status", "open")), unsafe_allow_html=True)
                    with st.expander("Raw JSON"):
                        st.json(data)
                else:
                    _display_response_rich(resp)
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_list:
        st.subheader("My Tickets")
        if st.button("\U0001f504 Load Tickets", width="stretch"):
            resp = _api_call("GET", "/tickets")
            _display_response_rich(resp)

    with tab_detail:
        st.markdown('<div class="aura-card">', unsafe_allow_html=True)
        st.subheader("Ticket Detail")
        detail_id = st.text_input("\U0001f194 Ticket ID")
        if st.button("\U0001f50d Get Ticket", width="stretch"):
            if not detail_id:
                st.warning("Enter a ticket ID.")
            else:
                resp = _api_call("GET", f"/tickets/{detail_id}")
                if 200 <= resp.status_code < 300:
                    data = resp.json()
                    st.markdown(f'**{data.get("subject","")}**')
                    st.markdown(
                        _ticket_status_badge(data.get("status", "")) + " " +
                        _badge_html(data.get("priority", ""), "badge-warning"),
                        unsafe_allow_html=True,
                    )
                    st.write(data.get("description", ""))
                    with st.expander("Raw JSON"):
                        st.json(data)
                else:
                    _display_response_rich(resp)
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_transition:
        st.markdown('<div class="aura-card">', unsafe_allow_html=True)
        st.subheader("Transition Ticket Status")

        # Styled state machine diagram
        st.markdown(
            '<div class="state-flow">'
            '<span class="state-box" style="background:#e8f0fe;color:#2c5282">OPEN</span>'
            '<span class="state-arrow">\u2192</span>'
            '<span class="state-box" style="background:#fef5e7;color:#b7791f">IN PROGRESS</span>'
            '<span class="state-arrow">\u2192</span>'
            '<span class="state-box" style="background:#e6f4ea;color:#1e7e34">RESOLVED</span>'
            '<span class="state-arrow">\u2192</span>'
            '<span class="state-box" style="background:#f0f0f0;color:#666">CLOSED</span>'
            '</div>'
            '<div style="margin-left:180px;margin-top:-8px">'
            '<span class="state-arrow">\u21b3</span>'
            '<span class="state-box" style="background:#f0f0f0;color:#666">CLOSED</span>'
            '</div>',
            unsafe_allow_html=True,
        )

        trans_id = st.text_input("\U0001f194 Ticket ID", key="trans_ticket_id")
        current_status = ""

        if trans_id:
            resp = _api_call("GET", f"/tickets/{trans_id}")
            if 200 <= resp.status_code < 300:
                current_status = resp.json().get("status", "")
                st.markdown(f'Current: {_ticket_status_badge(current_status)}', unsafe_allow_html=True)

                # Show allowed transitions as buttons
                allowed = VALID_TRANSITIONS.get(current_status, set())
                if allowed:
                    st.write("**Allowed transitions:**")
                    cols = st.columns(len(allowed))
                    for i, target in enumerate(sorted(allowed)):
                        if cols[i].button(f"\u27a1 {target}", key=f"trans_{target}"):
                            resp = _api_call("PATCH", f"/tickets/{trans_id}/status",
                                             json_data={"status": target})
                            if 200 <= resp.status_code < 300:
                                st.success(f"\u2705 Status changed to {target}!")
                                st.rerun()
                            else:
                                _display_response_rich(resp)
                else:
                    st.info("No transitions available (terminal state).")
            elif resp.status_code == 404:
                st.warning("Ticket not found.")

        st.markdown('</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Wellness Page
# ---------------------------------------------------------------------------


def _render_wellness() -> None:
    st.header("\U0001f338 Wellness Plans")
    if not _ensure_auth():
        return

    tab_generate, tab_list, tab_detail = st.tabs(["Generate Plan", "My Plans", "Plan Detail"])

    with tab_generate:
        st.markdown('<div class="aura-card">', unsafe_allow_html=True)
        st.subheader("\u2728 Generate Wellness Plan")
        st.markdown(
            '<div class="aura-card-dark" style="text-align:center">'
            '<span style="font-size:2rem">\U0001f512</span><br>'
            '<span>Premium feature — requires an active premium subscription.</span></div>',
            unsafe_allow_html=True,
        )
        wellness_lang = st.selectbox("\U0001f310 Language", ["en", "ar"], key="wellness_lang")
        if st.button("\U0001f9ed Generate", width="stretch"):
            resp = _api_call("POST", "/wellness/plan", json_data={"language": wellness_lang})
            if 200 <= resp.status_code < 300:
                data = resp.json()
                st.success("\u2705 Plan generated!")
                st.subheader(data.get("title", "Your Wellness Plan"))
                st.write(data.get("summary", ""))
                tasks = data.get("tasks", [])
                if tasks:
                    for i, task in enumerate(tasks):
                        if isinstance(task, dict):
                            st.markdown(f"**{i+1}. {task.get('task', task.get('title', ''))}**")
                            if task.get("frequency"):
                                st.caption(f"Frequency: {task['frequency']}")
                        else:
                            st.markdown(f"- {task}")
                with st.expander("Raw JSON"):
                    st.json(data)
            else:
                _display_response_rich(resp)
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_list:
        st.subheader("My Wellness Plans")
        if st.button("\U0001f504 Load Plans", width="stretch"):
            resp = _api_call("GET", "/wellness/plans")
            if 200 <= resp.status_code < 300:
                plans = resp.json()
                if plans:
                    for p in plans:
                        with st.expander(f"\U0001f338 {p.get('title', 'Untitled')}"):
                            st.write(p.get("description", ""))
                            st.markdown(
                                _badge_html(p.get("language", "").upper(), "badge-info") + " " +
                                _badge_html(f"{len(p.get('tasks', []))} tasks", "badge-plum"),
                                unsafe_allow_html=True,
                            )
                            st.caption(f"Created: {p.get('created_at', '')[:10]}")
                            st.caption(f"ID: `{p.get('id', '')}`")
                    with st.expander("Raw JSON"):
                        st.json(plans)
                else:
                    st.info("No plans yet.")
            else:
                _display_response_rich(resp)

    with tab_detail:
        st.markdown('<div class="aura-card">', unsafe_allow_html=True)
        st.subheader("Plan Detail")
        plan_id = st.text_input("\U0001f194 Plan ID")
        if st.button("\U0001f50d Get Plan", width="stretch"):
            if not plan_id:
                st.warning("Enter a plan ID.")
            else:
                resp = _api_call("GET", f"/wellness/plans/{plan_id}")
                if 200 <= resp.status_code < 300:
                    data = resp.json()
                    st.subheader(data.get("title", "Wellness Plan"))
                    st.write(data.get("description", ""))
                    tasks = data.get("tasks", [])
                    if tasks:
                        st.subheader("Tasks")
                        for i, task in enumerate(tasks):
                            if isinstance(task, dict):
                                st.markdown(f"**{i+1}. {task.get('task', task.get('title', ''))}**")
                                if task.get("frequency"):
                                    st.markdown(_badge_html(task["frequency"], "badge-rose"), unsafe_allow_html=True)
                            else:
                                st.markdown(f"- {task}")
                    with st.expander("Raw JSON"):
                        st.json(data)
                else:
                    _display_response_rich(resp)
        st.markdown('</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Cycle Tracker Page
# ---------------------------------------------------------------------------


CYCLE_SYMPTOMS = [
    "cramps", "headache", "bloating", "fatigue", "back pain",
    "acne", "mood swings", "breast tenderness", "nausea", "insomnia",
]


def _render_cycle_tracker() -> None:
    st.header("\U0001f338 Cycle Tracker")
    if not _ensure_auth():
        return

    tab_log, tab_cycles, tab_prediction = st.tabs(
        ["Log Period", "My Cycles", "Prediction"]
    )

    with tab_log:
        st.markdown('<div class="aura-card">', unsafe_allow_html=True)
        st.subheader("Log a Period Cycle")
        with st.form("cycle_log_form"):
            cl_start = st.date_input("\U0001f4c5 Start Date", value=date.today(), key="cl_start")
            cl_end = st.date_input("\U0001f4c5 End Date (optional)", value=None, key="cl_end")
            cl_cycle_len = st.number_input("\U0001f504 Cycle Length (days)", min_value=14, max_value=45, value=28)
            cl_period_len = st.number_input("\U0001f4a5 Period Length (days)", min_value=1, max_value=14, value=5)
            cl_mood = st.slider("\U0001f60a Mood (1-10)", 1, 10, value=5, key="cl_mood")
            cl_symptoms = st.multiselect("\U0001f3e5 Symptoms", CYCLE_SYMPTOMS, key="cl_symptoms")
            cl_notes = st.text_area("\U0001f4dd Notes", height=80, key="cl_notes")
            cl_submitted = st.form_submit_button("\u2705 Log Cycle")

        if cl_submitted:
            data: dict = {"start_date": str(cl_start), "cycle_length": cl_cycle_len, "period_length": cl_period_len}
            if cl_end:
                data["end_date"] = str(cl_end)
            data["mood"] = cl_mood
            if cl_symptoms:
                data["symptoms"] = cl_symptoms
            if cl_notes.strip():
                data["notes"] = cl_notes

            resp = _api_call("POST", "/cycles", json_data=data)
            if 200 <= resp.status_code < 300:
                st.success("\u2705 Cycle logged!")
                with st.expander("Raw JSON"):
                    st.json(resp.json())
            else:
                _display_response_rich(resp)
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_cycles:
        st.subheader("My Cycles")
        col_page, col_limit, col_load = st.columns([1, 1, 1])
        with col_page:
            cycle_page = st.number_input("\U0001f4c4 Page", min_value=1, value=1, key="cycle_page")
        with col_limit:
            cycle_limit = st.number_input("\U0001f4c4 Limit", min_value=1, max_value=100, value=10, key="cycle_limit")
        with col_load:
            st.markdown("<br>", unsafe_allow_html=True)
            load_clicked = st.button("\U0001f504 Load Cycles", width="stretch")

        if load_clicked:
            resp = _api_call("GET", "/cycles", params={"page": cycle_page, "limit": cycle_limit})
            if 200 <= resp.status_code < 300:
                cycles = resp.json()
                if isinstance(cycles, list) and cycles:
                    for c in cycles:
                        cycle_id = c.get("id", "")
                        with st.expander(
                            f"\U0001f4c5 {c.get('start_date', '?')} \u2192 {c.get('end_date', 'ongoing')}"
                        ):
                            col1, col2, col3 = st.columns(3)
                            col1.markdown(
                                f'<div class="aura-metric"><div class="metric-value">{c.get("cycle_length", "?")}</div>'
                                f'<div class="metric-label">Cycle Length</div></div>', unsafe_allow_html=True)
                            col2.markdown(
                                f'<div class="aura-metric"><div class="metric-value">{c.get("period_length", "?")}</div>'
                                f'<div class="metric-label">Period Length</div></div>', unsafe_allow_html=True)
                            col3.markdown(
                                f'<div class="aura-metric"><div class="metric-value">{c.get("mood", "?")}</div>'
                                f'<div class="metric-label">Mood</div></div>', unsafe_allow_html=True)

                            symptoms = c.get("symptoms", [])
                            if symptoms:
                                st.markdown(
                                    "**Symptoms:** " + " ".join(_badge_html(s, "badge-rose") for s in symptoms),
                                    unsafe_allow_html=True,
                                )
                            if c.get("notes"):
                                st.caption(f"\U0001f4dd {c['notes']}")

                            if st.button(f"\U0001f5d1 Delete", key=f"del_cycle_{cycle_id}"):
                                del_resp = _api_call("DELETE", f"/cycles/{cycle_id}")
                                if 200 <= del_resp.status_code < 300:
                                    st.success("Cycle deleted!")
                                    st.rerun()
                                else:
                                    _display_response_rich(del_resp)

                            st.caption(f"ID: `{cycle_id[:8]}...`")
                    with st.expander("Raw JSON"):
                        st.json(cycles)
                elif isinstance(cycles, list):
                    st.info("No cycles found. Log your first period!")
                else:
                    _display_response_rich(resp)
            else:
                _display_response_rich(resp)

    with tab_prediction:
        st.markdown('<div class="aura-card">', unsafe_allow_html=True)
        st.subheader("\U0001f52e Period Prediction")
        if st.button("\U0001f50d Get Prediction", width="stretch"):
            resp = _api_call("GET", "/cycles/prediction")
            if 200 <= resp.status_code < 300:
                data = resp.json()
                col1, col2, col3 = st.columns(3)
                col1.markdown(
                    f'<div class="aura-metric"><div class="metric-icon">\U0001f4c5</div>'
                    f'<div class="metric-value">{data.get("next_period_start", "?")}</div>'
                    f'<div class="metric-label">Next Period Start</div></div>', unsafe_allow_html=True)
                col2.markdown(
                    f'<div class="aura-metric"><div class="metric-icon">\U0001f4c5</div>'
                    f'<div class="metric-value">{data.get("next_period_end", "?")}</div>'
                    f'<div class="metric-label">Next Period End</div></div>', unsafe_allow_html=True)
                col3.markdown(
                    f'<div class="aura-metric"><div class="metric-icon">\u23f3</div>'
                    f'<div class="metric-value">{data.get("days_until_next", "?")}</div>'
                    f'<div class="metric-label">Days Until Next</div></div>', unsafe_allow_html=True)

                phase = data.get("current_phase", "")
                phase_desc = data.get("phase_description", "")
                if phase:
                    st.markdown(
                        f'<div class="aura-card-dark" style="text-align:center">'
                        f'<span style="font-size:1.5rem">\U0001f338 {phase.replace("_", " ").title()}</span><br>'
                        f'<span style="opacity:0.85">{phase_desc}</span></div>',
                        unsafe_allow_html=True,
                    )

                with st.expander("Raw JSON"):
                    st.json(data)
            elif resp.status_code == 404:
                st.info("No cycles logged yet. Log your first period to get predictions!")
            else:
                _display_response_rich(resp)
        st.markdown('</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Admin Page
# ---------------------------------------------------------------------------

# Admin emails that can access this page (must match ADMIN_EMAILS env var)
_ADMIN_EMAILS = [
    "osama@aura.health",
    "admin@aura.health",
]


def _render_admin() -> None:
    st.header("\U0001f511 Admin Dashboard")
    if not _ensure_auth():
        return

    user_email = st.session_state.get("user_email", "").lower()
    if user_email not in [e.lower() for e in _ADMIN_EMAILS]:
        st.error("\u26a0 You do not have admin access.")
        st.info("This page is restricted to admin users.")
        return

    tab_stats, tab_users, tab_interactions, tab_data = st.tabs(
        ["Stats Overview", "Users", "Interactions", "Data Management"]
    )

    with tab_stats:
        st.subheader("Platform Overview")
        if st.button("\U0001f4ca Load Stats", width="stretch"):
            resp = _api_call("GET", "/admin/stats")
            if 200 <= resp.status_code < 300:
                data = resp.json()
                col1, col2, col3 = st.columns(3)
                col1.metric("Users", data.get("users", 0))
                col1.metric("Conversations", data.get("conversations", 0))
                col2.metric("Messages", data.get("messages", 0))
                col2.metric("Analyses", data.get("analyses", 0))
                col3.metric("Cycle Entries", data.get("cycle_entries", 0))
                col3.metric("Health Logs", data.get("health_logs", 0))

                interactions = data.get("ai_interactions", {})
                st.markdown("### AI Interactions")
                ic1, ic2, ic3, ic4 = st.columns(4)
                ic1.metric("Chat", interactions.get("chat", 0))
                ic2.metric("Skin", interactions.get("skin", 0))
                ic3.metric("Report", interactions.get("report", 0))
                ic4.metric("Total", interactions.get("total", 0))

                subs = data.get("subscriptions", {})
                st.markdown("### Subscriptions")
                sc1, sc2 = st.columns(2)
                sc1.metric("Free", subs.get("free", 0))
                sc2.metric("Premium", subs.get("premium", 0))

                with st.expander("Raw JSON"):
                    st.json(data)
            else:
                _display_response_rich(resp)

    with tab_users:
        st.subheader("Users")
        col_search = st.columns(1)
        search_email = st.text_input("\U0001f50d Search by email", key="admin_user_search")
        page_num = st.number_input("Page", min_value=1, value=1, key="admin_users_page")
        page_limit = st.number_input("Limit", min_value=1, max_value=100, value=20, key="admin_users_limit")

        if st.button("\U0001f4da Load Users", width="stretch"):
            params = {"page": page_num, "limit": page_limit}
            if search_email:
                params["search"] = search_email
            resp = _api_call("GET", "/admin/users", params=params)
            if 200 <= resp.status_code < 300:
                data = resp.json()
                users = data.get("users", [])
                if users:
                    st.write(f"Showing {len(users)} users (Page {data.get('page', 1)})")
                    for u in users:
                        with st.expander(f"{u.get('email', 'Unknown')}"):
                            for k, v in u.items():
                                st.markdown(f"**{k}:** {v}")
                else:
                    st.info("No users found.")
            else:
                _display_response_rich(resp)

    with tab_interactions:
        st.subheader("AI Interaction Analytics")
        days = st.number_input("Days to look back", min_value=1, max_value=365, value=30, key="admin_interactions_days")
        if st.button("\U0001f4c8 Load Interactions", width="stretch"):
            resp = _api_call("GET", "/admin/interactions", params={"days": days})
            if 200 <= resp.status_code < 300:
                data = resp.json()
                daily = data.get("daily", [])
                if daily:
                    st.write(f"Last {days} days of interactions ({len(daily)} records)")
                    for entry in daily:
                        date_str = entry.get("date", "")
                        itype = entry.get("interaction_type", "")
                        count = entry.get("count", 0)
                        st.markdown(f"**{date_str}** — {itype}: {count}")
                else:
                    st.info("No interaction data found for this period.")
                with st.expander("Raw JSON"):
                    st.json(data)
            else:
                _display_response_rich(resp)

    with tab_data:
        st.subheader("\u26a0 Data Management")
        st.warning("This will permanently delete ALL application data for a user. Their account and subscription will NOT be deleted.")

        user_id_input = st.text_input("User ID to delete data for", key="admin_delete_user_id")
        if st.button("\U0001f5d1 Delete All User Data", type="primary", width="stretch"):
            if not user_id_input:
                st.error("Please enter a User ID.")
            else:
                resp = _api_call("DELETE", f"/admin/data/{user_id_input}")
                if 200 <= resp.status_code < 300:
                    data = resp.json()
                    tables_cleared = data.get("tables_cleared", [])
                    st.success(f"\u2705 Deleted all data for user {user_id_input}")
                    st.write(f"Tables cleared: {', '.join(tables_cleared)}")
                else:
                    _display_response_rich(resp)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

PAGES = {
    "Auth": _render_auth,
    "Profile & Me": _render_profile,
    "Chat": _render_chat,
    "Cycle Tracker": _render_cycle_tracker,
    "Health Log": _render_health_log,
    "Subscriptions": _render_subscriptions,
    "Tickets": _render_tickets,
    "Wellness": _render_wellness,
    "Admin": _render_admin,
}

st.set_page_config(
    page_title="Aura Health - Test Dashboard",
    page_icon="\U0001f338",
    layout="wide",
    initial_sidebar_state="expanded",
)
_inject_css()
_render_sidebar()
page = st.session_state.get("page", "Auth")
PAGES[page]()