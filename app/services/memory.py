"""Fetch past analyses and conversations to build ambient context for the AI."""

from __future__ import annotations

import json
from datetime import date, timedelta

from app.db.supabase import supabase_admin


async def build_summary_context(user_id: str) -> str:
    """Build a summary string from the user's last 3 analyses and last conversation title."""
    parts: list[str] = []

    # Fetch last 3 analyses
    analyses_resp = (
        supabase_admin.table("analyses")
        .select("analysis_type, result, created_at")
        .eq("user_id", user_id)
        .eq("status", "completed")
        .order("created_at", desc=True)
        .limit(3)
        .execute()
    )

    if analyses_resp.data:
        for a in analyses_resp.data:
            a_type = a.get("analysis_type", "unknown")
            created = a.get("created_at", "")
            result = a.get("result", {})
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    result = {}

            if a_type == "skin":
                concern = result.get("concern", "unknown concern")
                parts.append(f"Skin analysis: {concern} ({created})")
            elif a_type == "report":
                summary = result.get("summary", "unknown report")
                parts.append(f"Report analysis: {summary} ({created})")
            else:
                parts.append(f"{a_type} analysis ({created})")

    # Fetch last conversation title
    conv_resp = (
        supabase_admin.table("conversations")
        .select("title")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    if conv_resp.data:
        title = conv_resp.data[0].get("title", "")
        if title:
            parts.append(f"Last conversation: {title}")

    return "; ".join(parts) if parts else ""


def build_cycle_context(user_id: str) -> str:
    """Build a cycle-aware context string from the user's menstrual cycle data."""
    cycles_resp = (
        supabase_admin.table("menstrual_cycles")
        .select("start_date, end_date, cycle_length, period_length, symptoms")
        .eq("user_id", user_id)
        .order("start_date", desc=True)
        .limit(3)
        .execute()
    )

    if not cycles_resp.data:
        return ""

    latest = cycles_resp.data[0]
    start_date_str = latest.get("start_date", "")
    cycle_length = latest.get("cycle_length", 28)

    try:
        start_date = date.fromisoformat(start_date_str) if start_date_str else None
    except (ValueError, TypeError):
        return ""

    if not start_date:
        return ""

    today = date.today()
    days_since_start = (today - start_date).days
    cycle_length = cycle_length or 28

    # Determine current phase
    if days_since_start < 0:
        phase = "between cycles"
        phase_desc = "Awaiting next period"
    elif days_since_start < 6:
        phase = "menstrual"
        phase_desc = "Your period — rest and self-care"
    elif days_since_start < 14:
        phase = "follicular"
        phase_desc = "Energy rising — great for new projects"
    elif days_since_start == 14:
        phase = "ovulation"
        phase_desc = "Peak energy and focus"
    else:
        phase = "luteal"
        phase_desc = "Wind down — prioritize rest"

    # Predict next period
    next_period_start = start_date + timedelta(days=cycle_length)
    days_until_next = (next_period_start - today).days

    # Average cycle length across entries
    cycle_lengths = [
        c.get("cycle_length", 28) for c in cycles_resp.data if c.get("cycle_length")
    ]
    avg_cycle = round(sum(cycle_lengths) / len(cycle_lengths)) if cycle_lengths else 28

    context = (
        f"User is on day {days_since_start + 1} of their menstrual cycle "
        f"({phase} phase: {phase_desc}). "
        f"Average cycle length: {avg_cycle} days. "
        f"Next period predicted in {days_until_next} days."
    )

    symptoms = latest.get("symptoms", [])
    if symptoms and isinstance(symptoms, list) and len(symptoms) > 0:
        context += f" Reported symptoms this cycle: {', '.join(symptoms[:5])}."

    return context


async def get_conversation_analysis(
    conversation_id: str, user_id: str
) -> tuple[dict | None, str | None]:
    """Fetch the latest analysis from a conversation.

    Queries the messages table for the latest message with an analysis_id,
    then fetches the full analysis record from the analyses table.

    Returns:
        (result_dict, analysis_type) if found, (None, None) otherwise.
    """
    # Find the latest message with an analysis_id in this conversation
    msgs_resp = (
        supabase_admin.table("messages")
        .select("analysis_id")
        .eq("conversation_id", conversation_id)
        .eq("user_id", user_id)
        .is_("analysis_id", "not_null")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    if not msgs_resp.data:
        return None, None

    analysis_id = msgs_resp.data[0].get("analysis_id")

    # Fetch the analysis record
    analysis_resp = (
        supabase_admin.table("analyses")
        .select("analysis_type, result")
        .eq("id", analysis_id)
        .execute()
    )

    if not analysis_resp.data:
        return None, None

    analysis = analysis_resp.data[0]
    result = analysis.get("result", {})
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            result = {}

    return result, analysis.get("analysis_type")
