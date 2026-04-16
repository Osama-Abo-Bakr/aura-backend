"""
Aura Health API — Streamlit Test Dashboard

A local testing UI for all Aura backend endpoints.
Configure API_URL via environment variable (defaults to http://localhost:8000).
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime

import httpx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

API_URL = os.environ.get("API_URL", "http://localhost:8000")
API_PREFIX = f"{API_URL}/api/v1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _headers() -> dict[str, str]:
    """Return auth headers if logged in, else empty dict."""
    token = st.session_state.get("access_token")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def _api_call(method: str, path: str, *, json_data=None, params=None) -> httpx.Response:
    """Make an API call and return the response."""
    url = f"{API_PREFIX}{path}"
    resp = httpx.request(method, url, json=json_data, params=params, headers=_headers(), timeout=30)
    return resp


def _display_response(resp: httpx.Response) -> None:
    """Display an API response in a friendly format."""
    if 200 <= resp.status_code < 300:
        st.success(f"**{resp.status_code}** — OK")
    elif resp.status_code == 422:
        st.error(f"**{resp.status_code}** — Validation Error")
        data = resp.json()
        if "errors" in data:
            for err in data["errors"]:
                st.warning(f"`{err.get('field', '?')}`: {err.get('message', '?')}")
        else:
            st.json(data)
        return
    else:
        st.error(f"**{resp.status_code}**")
    try:
        st.json(resp.json())
    except Exception:
        st.code(resp.text)


def _ensure_auth() -> bool:
    """Check if user is authenticated. Show warning if not."""
    if not st.session_state.get("access_token"):
        st.warning("Please log in first (see Auth page).")
        return False
    return True


# ---------------------------------------------------------------------------
# Sidebar — Auth Status & Navigation
# ---------------------------------------------------------------------------


def _render_sidebar() -> None:
    """Render sidebar with auth status and page navigation."""
    with st.sidebar:
        st.title("Aura Health")
        st.caption("Backend Test Dashboard")

        st.divider()

        # Auth status
        if st.session_state.get("access_token"):
            st.success(f"Logged in as: {st.session_state.get('user_email', 'unknown')}")
            if st.button("Sign Out"):
                _do_signout()
        else:
            st.info("Not logged in")

        st.divider()

        # Navigation
        page = st.radio(
            "Navigate",
            ["Auth", "Profile & Me", "Chat", "Analysis", "Health Log", "Subscriptions", "Tickets", "Wellness"],
            label_visibility="collapsed",
        )
        st.session_state["page"] = page

        st.divider()
        st.caption(f"API: `{API_URL}`")


def _do_signout() -> None:
    """Call signout endpoint and clear session state."""
    resp = _api_call("POST", "/auth/signout")
    for key in ["access_token", "refresh_token", "user_email"]:
        st.session_state.pop(key, None)
    if 200 <= resp.status_code < 300:
        st.sidebar.success("Signed out!")
    else:
        st.sidebar.warning(f"Signout returned {resp.status_code}, session cleared locally.")


# ---------------------------------------------------------------------------
# Auth Page
# ---------------------------------------------------------------------------


def _render_auth() -> None:
    """Render Auth page with Register, Login, Refresh, Signout."""
    st.header("Authentication")

    tab_reg, tab_login, tab_refresh = st.tabs(["Register", "Login", "Refresh Token"])

    # ---- Register ----
    with tab_reg:
        st.subheader("Register New User")
        with st.form("register_form"):
            reg_email = st.text_input("Email", key="reg_email")
            reg_password = st.text_input("Password", type="password", key="reg_password")
            reg_name = st.text_input("Full Name", key="reg_name")
            reg_submitted = st.form_submit_button("Register")

        if reg_submitted:
            if not reg_email or not reg_password or not reg_name:
                st.warning("All fields are required.")
            else:
                resp = _api_call("POST", "/auth/register", json_data={
                    "email": reg_email,
                    "password": reg_password,
                    "full_name": reg_name,
                })
                _display_response(resp)

    # ---- Login ----
    with tab_login:
        st.subheader("Sign In")
        with st.form("login_form"):
            login_email = st.text_input("Email", key="login_email")
            login_password = st.text_input("Password", type="password", key="login_password")
            login_submitted = st.form_submit_button("Sign In")

        if login_submitted:
            if not login_email or not login_password:
                st.warning("Email and password are required.")
            else:
                resp = _api_call("POST", "/auth/token", json_data={
                    "email": login_email,
                    "password": login_password,
                })
                if 200 <= resp.status_code < 300:
                    data = resp.json()
                    st.session_state["access_token"] = data["access_token"]
                    st.session_state["refresh_token"] = data["refresh_token"]
                    st.session_state["user_email"] = login_email
                    st.success("Logged in successfully!")
                    st.json(data)
                else:
                    _display_response(resp)

    # ---- Refresh ----
    with tab_refresh:
        st.subheader("Refresh Token")
        refresh_token = st.text_input("Refresh Token", value=st.session_state.get("refresh_token", ""), key="refresh_input")
        if st.button("Refresh"):
            if not refresh_token:
                st.warning("No refresh token available.")
            else:
                resp = _api_call("POST", "/auth/refresh", json_data={"refresh_token": refresh_token})
                if 200 <= resp.status_code < 300:
                    data = resp.json()
                    st.session_state["access_token"] = data["access_token"]
                    st.session_state["refresh_token"] = data["refresh_token"]
                    st.success("Token refreshed!")
                    st.json(data)
                else:
                    _display_response(resp)

    # ---- Current tokens ----
    st.divider()
    st.subheader("Session Info")
    if st.session_state.get("access_token"):
        st.text_input("Access Token", value=st.session_state["access_token"], disabled=True)
        st.text_input("Refresh Token", value=st.session_state.get("refresh_token", ""), disabled=True)
    else:
        st.info("No active session. Log in above.")


# ---------------------------------------------------------------------------
# Profile & Me Page
# ---------------------------------------------------------------------------


def _render_profile() -> None:
    """Render Profile & Me page."""
    st.header("Profile & Me")
    if not _ensure_auth():
        return

    tab_me, tab_upsert = st.tabs(["Get Me", "Upsert Profile"])

    with tab_me:
        if st.button("Fetch /me"):
            resp = _api_call("GET", "/me")
            _display_response(resp)

    with tab_upsert:
        st.subheader("Create or Update Profile")
        with st.form("profile_form"):
            p_name = st.text_input("Full Name")
            p_lang = st.selectbox("Language", ["ar", "en"])
            p_country = st.text_input("Country (2-letter code)", max_chars=2)
            p_dob = st.date_input("Date of Birth", value=None, format="YYYY-MM-DD")
            p_goals = st.text_input("Health Goals (comma-separated)")
            p_conditions = st.text_input("Conditions (comma-separated)")
            p_submitted = st.form_submit_button("Upsert Profile")

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
            _display_response(resp)


# ---------------------------------------------------------------------------
# Chat Page
# ---------------------------------------------------------------------------


def _render_chat() -> None:
    """Render Chat page with SSE streaming."""
    st.header("Chat")
    if not _ensure_auth():
        return

    tab_send, tab_convos = st.tabs(["Send Message", "Conversations"])

    # ---- Send Message (SSE) ----
    with tab_send:
        st.subheader("Send a Message")

        # Load conversations for dropdown
        convos = []
        try:
            resp = _api_call("GET", "/chat/conversations")
            if 200 <= resp.status_code < 300:
                convos = resp.json()
        except Exception:
            pass

        convo_options = ["New Conversation"] + [
            f"{c['id']} — {c.get('title', 'Untitled')}" for c in convos
        ]
        selected_convo = st.selectbox("Conversation", convo_options, index=0)
        convo_id = None if selected_convo == "New Conversation" else selected_convo.split(" — ")[0]

        chat_lang = st.selectbox("Language", ["en", "ar"], index=0)
        chat_msg = st.text_area("Message", height=100)

        if st.button("Send"):
            if not chat_msg.strip():
                st.warning("Enter a message.")
            else:
                payload: dict = {"content": chat_msg, "language": chat_lang}
                if convo_id:
                    payload["conversation_id"] = convo_id

                url = f"{API_PREFIX}/chat/message"
                headers = _headers()
                headers["Accept"] = "text/event-stream"

                response_text = ""
                with st.spinner("Streaming response..."):
                    with httpx.stream("POST", url, json=payload, headers=headers, timeout=60) as stream:
                        for line in stream.iter_lines():
                            if line.startswith("data: "):
                                data = line[6:]
                                if data == "[DONE]":
                                    break
                                response_text += data

                st.markdown("### Assistant Response")
                st.write(response_text)

    # ---- Conversations ----
    with tab_convos:
        col1, col2 = st.columns([3, 1])
        with col1:
            if st.button("Refresh Conversations"):
                resp = _api_call("GET", "/chat/conversations")
                if 200 <= resp.status_code < 300:
                    st.session_state["chat_convos"] = resp.json()
                else:
                    _display_response(resp)

        convos = st.session_state.get("chat_convos", [])
        if convos:
            for c in convos:
                with st.expander(f"{c.get('title', 'Untitled')} — {c['id'][:8]}"):
                    st.write(f"Language: {c.get('language', '?')} | Messages: {c.get('message_count', 0)} | Created: {c.get('created_at', '?')}")

                    if st.button("View Messages", key=f"view_{c['id']}"):
                        resp = _api_call("GET", f"/chat/conversations/{c['id']}/messages")
                        _display_response(resp)

                    if st.button("Delete", key=f"del_{c['id']}"):
                        resp = _api_call("DELETE", f"/chat/conversations/{c['id']}")
                        _display_response(resp)
                        st.session_state.pop("chat_convos", None)
        else:
            st.info("No conversations yet. Click Refresh to load.")


# ---------------------------------------------------------------------------
# Analysis Page
# ---------------------------------------------------------------------------


def _render_analysis() -> None:
    """Render Analysis page."""
    st.header("Analysis")
    if not _ensure_auth():
        return

    tab_upload, tab_submit, tab_status, tab_history = st.tabs(
        ["Upload URL", "Submit Analysis", "Check Status", "History"]
    )

    with tab_upload:
        st.subheader("Generate Upload URL")
        with st.form("upload_url_form"):
            file_name = st.text_input("File Name", value="test.jpg")
            content_type = st.selectbox("Content Type", [
                "image/jpeg", "image/png", "image/webp", "image/heic", "application/pdf"
            ])
            analysis_type = st.selectbox("Analysis Type", ["skin", "report"])
            upload_submitted = st.form_submit_button("Get Upload URL")

        if upload_submitted:
            resp = _api_call("POST", "/analysis/upload-url", json_data={
                "file_name": file_name,
                "content_type": content_type,
                "analysis_type": analysis_type,
            })
            _display_response(resp)

    with tab_submit:
        st.subheader("Submit Analysis")
        analysis_lang = st.selectbox("Language", ["en", "ar"], key="analysis_lang")
        file_path = st.text_input("File Path (from upload URL response)")

        col_skin, col_report = st.columns(2)
        with col_skin:
            if st.button("Skin Analysis"):
                if not file_path:
                    st.warning("Enter a file path.")
                else:
                    resp = _api_call("POST", "/analysis/skin", json_data={
                        "file_path": file_path, "language": analysis_lang,
                    })
                    _display_response(resp)

        with col_report:
            if st.button("Report Analysis"):
                if not file_path:
                    st.warning("Enter a file path.")
                else:
                    resp = _api_call("POST", "/analysis/report", json_data={
                        "file_path": file_path, "language": analysis_lang,
                    })
                    _display_response(resp)

    with tab_status:
        st.subheader("Check Analysis Status")
        status_id = st.text_input("Analysis ID")
        if st.button("Check Status"):
            if not status_id:
                st.warning("Enter an analysis ID.")
            else:
                resp = _api_call("GET", f"/analysis/{status_id}/status")
                _display_response(resp)

    with tab_history:
        st.subheader("Analysis History")
        page_num = st.number_input("Page", min_value=1, value=1, key="hist_page")
        page_limit = st.number_input("Limit", min_value=1, max_value=50, value=10, key="hist_limit")
        if st.button("Load History"):
            resp = _api_call("GET", "/analysis/history", params={"page": page_num, "limit": page_limit})
            _display_response(resp)


# ---------------------------------------------------------------------------
# Health Log Page
# ---------------------------------------------------------------------------


def _render_health_log() -> None:
    """Render Health Log page with charts."""
    st.header("Health Log")
    if not _ensure_auth():
        return

    tab_upsert, tab_list, tab_summary, tab_date = st.tabs(
        ["Log Entry", "List Logs", "Summary & Charts", "Get / Delete by Date"]
    )

    with tab_upsert:
        st.subheader("Create / Update Log Entry")
        with st.form("health_log_form"):
            hl_date = st.date_input("Date", value=date.today())
            hl_mood = st.slider("Mood (1-10)", 1, 10, value=5)
            hl_energy = st.slider("Energy (1-10)", 1, 10, value=5)
            hl_sleep = st.slider("Sleep Hours (0-24)", 0.0, 24.0, value=7.0, step=0.5)
            hl_water = st.number_input("Water (ml)", min_value=0, value=0)
            hl_exercise = st.number_input("Exercise (minutes)", min_value=0, value=0)
            hl_symptoms = st.text_input("Symptoms (comma-separated)")
            hl_notes = st.text_area("Notes", height=80)
            hl_submitted = st.form_submit_button("Save Log")

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
            _display_response(resp)

    with tab_list:
        st.subheader("Recent Logs")
        hl_days = st.number_input("Days", min_value=1, max_value=365, value=30, key="hl_days")
        if st.button("Load Logs"):
            resp = _api_call("GET", "/health-log", params={"days": hl_days})
            _display_response(resp)

    with tab_summary:
        st.subheader("Health Summary & Charts")
        summary_days = st.slider("Days", min_value=7, max_value=90, value=30, key="summary_days")
        if st.button("Load Summary"):
            resp = _api_call("GET", "/health-log/summary", params={"days": summary_days})
            if 200 <= resp.status_code < 300:
                data = resp.json()

                st.metric("Days Tracked", data.get("entry_count", 0))
                st.metric("Total Exercise (min)", data.get("exercise_total_minutes", 0))
                st.metric("Avg Water (ml)", round(data.get("water_avg_ml", 0)))

                # Mood trend chart
                mood_trend = data.get("mood_trend", [])
                if mood_trend:
                    fig_mood = go.Figure()
                    fig_mood.add_trace(go.Scatter(
                        x=[d["date"] for d in mood_trend],
                        y=[d["value"] for d in mood_trend],
                        mode="lines+markers",
                        name="Mood",
                        line=dict(color="#636efa"),
                    ))
                    fig_mood.update_layout(title="Mood Trend", yaxis_range=[1, 10])
                    st.plotly_chart(fig_mood, use_container_width=True)

                # Energy trend chart
                energy_trend = data.get("energy_trend", [])
                if energy_trend:
                    fig_energy = go.Figure()
                    fig_energy.add_trace(go.Scatter(
                        x=[d["date"] for d in energy_trend],
                        y=[d["value"] for d in energy_trend],
                        mode="lines+markers",
                        name="Energy",
                        line=dict(color="#00cc96"),
                    ))
                    fig_energy.update_layout(title="Energy Trend", yaxis_range=[1, 10])
                    st.plotly_chart(fig_energy, use_container_width=True)

                # Sleep trend chart
                sleep_trend = data.get("sleep_trend", [])
                if sleep_trend:
                    fig_sleep = go.Figure()
                    fig_sleep.add_trace(go.Bar(
                        x=[d["date"] for d in sleep_trend],
                        y=[d["value"] for d in sleep_trend],
                        name="Sleep Hours",
                        marker_color="#ab63fa",
                    ))
                    fig_sleep.update_layout(title="Sleep Trend", yaxis_range=[0, 24])
                    st.plotly_chart(fig_sleep, use_container_width=True)

                # Symptom frequency
                symptoms = data.get("symptom_frequency", [])
                if symptoms:
                    fig_sym = go.Figure()
                    fig_sym.add_trace(go.Bar(
                        x=[s["symptom"] for s in symptoms],
                        y=[s["count"] for s in symptoms],
                        marker_color="#ef553b",
                    ))
                    fig_sym.update_layout(title="Symptom Frequency")
                    st.plotly_chart(fig_sym, use_container_width=True)
            else:
                _display_response(resp)

    with tab_date:
        st.subheader("Get / Delete by Date")
        lookup_date = st.date_input("Date", value=date.today(), key="hl_lookup_date")
        col_get, col_del = st.columns(2)
        with col_get:
            if st.button("Get Log"):
                resp = _api_call("GET", f"/health-log/{lookup_date}")
                _display_response(resp)
        with col_del:
            if st.button("Delete Log"):
                resp = _api_call("DELETE", f"/health-log/{lookup_date}")
                _display_response(resp)


# ---------------------------------------------------------------------------
# Subscriptions Page
# ---------------------------------------------------------------------------


def _render_subscriptions() -> None:
    """Render Subscriptions page."""
    st.header("Subscriptions")
    if not _ensure_auth():
        return

    tab_status, tab_checkout = st.tabs(["Status", "Checkout"])

    with tab_status:
        st.subheader("Subscription Status")
        if st.button("Check Status"):
            resp = _api_call("GET", "/subscribe/status")
            _display_response(resp)

    with tab_checkout:
        st.subheader("Start Premium Checkout")
        st.info("This will create a Stripe Checkout session and return a redirect URL.")
        if st.button("Create Checkout Session"):
            resp = _api_call("POST", "/subscribe/checkout")
            _display_response(resp)


# ---------------------------------------------------------------------------
# Tickets Page
# ---------------------------------------------------------------------------


VALID_TRANSITIONS = {
    "open": {"in_progress"},
    "in_progress": {"resolved", "closed"},
    "resolved": {"closed"},
    "closed": set(),
}


def _render_tickets() -> None:
    """Render Tickets page with state machine visualization."""
    st.header("Tickets")
    if not _ensure_auth():
        return

    tab_create, tab_list, tab_detail, tab_transition = st.tabs(
        ["Create", "List", "Detail", "Transition Status"]
    )

    with tab_create:
        st.subheader("Create Ticket")
        with st.form("ticket_create_form"):
            t_subject = st.text_input("Subject", max_chars=200)
            t_desc = st.text_area("Description", height=120, max_chars=5000)
            t_priority = st.selectbox("Priority", ["low", "medium", "high"])
            t_submitted = st.form_submit_button("Create Ticket")

        if t_submitted:
            if not t_subject or not t_desc:
                st.warning("Subject and description are required.")
            else:
                resp = _api_call("POST", "/tickets", json_data={
                    "subject": t_subject,
                    "description": t_desc,
                    "priority": t_priority,
                })
                _display_response(resp)

    with tab_list:
        st.subheader("My Tickets")
        if st.button("Load Tickets"):
            resp = _api_call("GET", "/tickets")
            _display_response(resp)

    with tab_detail:
        st.subheader("Ticket Detail")
        detail_id = st.text_input("Ticket ID")
        if st.button("Get Ticket"):
            if not detail_id:
                st.warning("Enter a ticket ID.")
            else:
                resp = _api_call("GET", f"/tickets/{detail_id}")
                _display_response(resp)

    with tab_transition:
        st.subheader("Transition Ticket Status")

        # State machine diagram
        st.markdown("**State Machine:**")
        st.markdown(
            "```text\n"
            "open → in_progress → resolved → closed\n"
            "                  └──→ closed\n"
            "```"
        )

        trans_id = st.text_input("Ticket ID", key="trans_ticket_id")
        current_status = st.text_input("Current Status (for reference)", disabled=True, value="", key="trans_current_status")

        # If we have a ticket ID, try to fetch current status
        if trans_id:
            resp = _api_call("GET", f"/tickets/{trans_id}")
            if 200 <= resp.status_code < 300:
                current_status = resp.json().get("status", "")
                st.info(f"Current status: **{current_status}**")

        new_status = st.selectbox("New Status", ["open", "in_progress", "resolved", "closed"])
        if st.button("Transition"):
            if not trans_id:
                st.warning("Enter a ticket ID.")
            else:
                resp = _api_call("PATCH", f"/tickets/{trans_id}/status", json_data={"status": new_status})
                _display_response(resp)


# ---------------------------------------------------------------------------
# Wellness Page
# ---------------------------------------------------------------------------


def _render_wellness() -> None:
    """Render Wellness page."""
    st.header("Wellness Plans")
    if not _ensure_auth():
        return

    tab_generate, tab_list, tab_detail = st.tabs(["Generate Plan", "My Plans", "Plan Detail"])

    with tab_generate:
        st.subheader("Generate Wellness Plan")
        st.warning("Premium feature — requires an active premium subscription.")
        wellness_lang = st.selectbox("Language", ["en", "ar"], key="wellness_lang")
        if st.button("Generate"):
            resp = _api_call("POST", "/wellness/plan", json_data={"language": wellness_lang})
            _display_response(resp)

    with tab_list:
        st.subheader("My Wellness Plans")
        if st.button("Load Plans"):
            resp = _api_call("GET", "/wellness/plans")
            _display_response(resp)

    with tab_detail:
        st.subheader("Plan Detail")
        plan_id = st.text_input("Plan ID")
        if st.button("Get Plan"):
            if not plan_id:
                st.warning("Enter a plan ID.")
            else:
                resp = _api_call("GET", f"/wellness/plans/{plan_id}")
                _display_response(resp)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

PAGES = {
    "Auth": _render_auth,
    "Profile & Me": _render_profile,
    "Chat": _render_chat,
    "Analysis": _render_analysis,
    "Health Log": _render_health_log,
    "Subscriptions": _render_subscriptions,
    "Tickets": _render_tickets,
    "Wellness": _render_wellness,
}


st.set_page_config(page_title="Aura Health API", page_icon="https://cdn-icons-png.flaticon.com/512/2965/2965567.png", layout="wide")
_render_sidebar()
page = st.session_state.get("page", "Auth")
PAGES[page]()