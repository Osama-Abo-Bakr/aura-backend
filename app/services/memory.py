"""Fetch past analyses and conversations to build ambient context for the AI."""

from __future__ import annotations

import json

from app.db.supabase import supabase_admin


async def build_summary_context(user_id: str) -> str:
    """Build a summary string from the user's last 3 analyses and last conversation title."""
    parts: list[str] = []

    # Fetch last 3 analyses
    analyses_resp = (
        supabase_admin
        .table("analyses")
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
        supabase_admin
        .table("conversations")
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