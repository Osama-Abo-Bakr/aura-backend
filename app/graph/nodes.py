"""LangGraph node functions for the conversation graph.

Each node is a pure function that takes ConversationState and returns a partial state dict.
"""

from __future__ import annotations

import json
import logging

from app.db.supabase import supabase_admin
from app.graph.prompts import (
    ANALYSIS_FOLLOWUP_TEMPLATE,
    CYCLE_CONTEXT_TEMPLATE,
    HEALTH_SYSTEM_PROMPT,
    MEMORY_CONTEXT_TEMPLATE,
)
from app.graph.state import ConversationState
from app.services.gemini import (
    analyze_skin,
    explain_medical_report,
    stream_chat_response,
)
from app.services.memory import build_summary_context, build_cycle_context
from app.services.storage import download_file

logger = logging.getLogger(__name__)

IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic"}
REPORT_TYPES = {"application/pdf"}


async def memory_injection(state: ConversationState) -> dict:
    """Inject ambient context from the user's past analyses, conversations, and cycle data."""
    user_id = state["user_id"]
    summary = await build_summary_context(user_id=user_id)
    cycle = build_cycle_context(user_id=user_id)
    return {"summary_context": summary, "cycle_context": cycle}


def router(state: ConversationState) -> str:
    """Determine which node to route to based on file type.

    Returns: "skin" | "report" | "chat"
    """
    current_file = state.get("current_file")
    if current_file is None:
        return "chat"

    file_type = current_file.get("file_type", "")
    if file_type in IMAGE_TYPES:
        return "skin"
    if file_type in REPORT_TYPES:
        return "report"

    return "chat"


async def skin_analyzer(state: ConversationState) -> dict:
    """Analyze a skin image using Gemini Vision."""
    current_file = state["current_file"]
    language = state["language"]
    user_id = state["user_id"]
    notes = state["current_message"] if state["current_message"] else None

    try:
        # Download file from Supabase Storage
        file_bytes, mime_type = await download_file(current_file["file_path"])

        # Call Gemini Vision
        result = await analyze_skin(
            image_bytes=file_bytes,
            mime_type=mime_type or current_file["file_type"],
            language=language,
            notes=notes,
        )

        # Store analysis in database
        analysis_resp = (
            supabase_admin.table("analyses")
            .insert(
                {
                    "user_id": user_id,
                    "analysis_type": "skin",
                    "file_path": current_file["file_path"],
                    "language": language,
                    "status": "completed",
                    "result": result,
                }
            )
            .execute()
        )
        analysis_id = analysis_resp.data[0]["id"]

        # Record quota usage
        supabase_admin.table("ai_interactions").insert(
            {
                "user_id": user_id,
                "interaction_type": "skin",
            }
        ).execute()

        # Build response text from analysis
        response_text = _format_skin_response(result, language)

        return {
            "last_analysis": result,
            "last_analysis_type": "skin",
            "response_chunks": [response_text],
            "analysis_meta": {"analysis_type": "skin", "analysis_id": analysis_id},
        }

    except Exception as e:
        logger.error(f"Skin analysis failed: {e}")
        return {
            "error": f"Skin analysis failed: {str(e)}",
            "response_chunks": [
                "I'm sorry, I couldn't analyze the image. Please try again."
            ],
        }


async def report_analyzer(state: ConversationState) -> dict:
    """Analyze a medical report using Gemini Vision."""
    current_file = state["current_file"]
    language = state["language"]
    user_id = state["user_id"]
    notes = state.get("current_message")

    try:
        # Download file from Supabase Storage
        file_bytes, mime_type = await download_file(current_file["file_path"])

        # Call Gemini Vision
        result = await explain_medical_report(
            file_bytes=file_bytes,
            mime_type=mime_type or current_file["file_type"],
            language=language,
            report_type=None,
            notes=notes,
        )

        # Store analysis in database
        analysis_resp = (
            supabase_admin.table("analyses")
            .insert(
                {
                    "user_id": user_id,
                    "analysis_type": "report",
                    "file_path": current_file["file_path"],
                    "language": language,
                    "status": "completed",
                    "result": result,
                }
            )
            .execute()
        )
        analysis_id = analysis_resp.data[0]["id"]

        # Record quota usage
        supabase_admin.table("ai_interactions").insert(
            {
                "user_id": user_id,
                "interaction_type": "report",
            }
        ).execute()

        # Build response text from analysis
        response_text = _format_report_response(result, language)

        return {
            "last_analysis": result,
            "last_analysis_type": "report",
            "response_chunks": [response_text],
            "analysis_meta": {"analysis_type": "report", "analysis_id": analysis_id},
        }

    except Exception as e:
        logger.error(f"Report analysis failed: {e}")
        return {
            "error": f"Report analysis failed: {str(e)}",
            "response_chunks": [
                "I'm sorry, I couldn't analyze the report. Please try again."
            ],
        }


async def chat_responder(state: ConversationState) -> dict:
    """Generate a conversational response using Gemini chat."""
    language = state["language"]
    messages = state.get("messages", [])
    current_message = state["current_message"]
    summary_context = state.get("summary_context", "")
    cycle_context = state.get("cycle_context", "")
    last_analysis = state.get("last_analysis")
    last_analysis_type = state.get("last_analysis_type")

    # Build system prompt with context
    system_prompt = HEALTH_SYSTEM_PROMPT
    if summary_context:
        system_prompt += "\n\n" + MEMORY_CONTEXT_TEMPLATE.format(
            summary=summary_context
        )
    if cycle_context:
        system_prompt += "\n\n" + CYCLE_CONTEXT_TEMPLATE.format(
            cycle_info=cycle_context
        )
    if last_analysis and last_analysis_type:
        system_prompt += "\n\n" + ANALYSIS_FOLLOWUP_TEMPLATE.format(
            analysis_type=last_analysis_type,
            analysis_result=json.dumps(last_analysis, indent=2),
        )

    # Prepare messages for Gemini
    gemini_messages = []
    for msg in messages[-20:]:
        role = "model" if msg.get("role") == "assistant" else "user"
        gemini_messages.append({"role": role, "content": msg.get("content", "")})

    # Add current message
    gemini_messages.append({"role": "user", "content": current_message})

    # Stream response and collect chunks
    chunks = []
    async for chunk in stream_chat_response(
        gemini_messages, language, system_prompt_override=system_prompt
    ):
        chunks.append(chunk)

    return {"response_chunks": chunks}


def response_formatter(state: ConversationState) -> dict:
    """Normalize the output state. This node exists as a convergence point in the graph."""
    return {}


# --- Helper functions ---


def _format_skin_response(result: dict, language: str) -> str:
    """Format skin analysis result as a readable text response."""
    lines = []
    if result.get("concern"):
        lines.append(f"**Concern:** {result['concern']}")
    if result.get("severity"):
        lines.append(f"**Severity:** {result['severity']}")
    if result.get("description"):
        lines.append(f"\n{result['description']}")
    if result.get("natural_remedies"):
        lines.append("\n**Natural Remedies:**")
        for remedy in result["natural_remedies"]:
            lines.append(f"- {remedy}")
    if result.get("skincare_routine"):
        lines.append("\n**Skincare Routine:**")
        for step in result["skincare_routine"]:
            lines.append(f"- {step}")
    if result.get("see_doctor"):
        lines.append(
            f"\n**See a doctor:** Yes — {result.get('doctor_reason', 'Recommended')}"
        )
    if result.get("disclaimer"):
        lines.append(f"\n*{result['disclaimer']}*")
    return "\n".join(lines) if lines else json.dumps(result, indent=2)


def _format_report_response(result: dict, language: str) -> str:
    """Format report analysis result as a readable text response."""
    lines = []
    if result.get("summary"):
        lines.append(f"**Summary:** {result['summary']}")
    if result.get("findings"):
        lines.append("\n**Findings:**")
        for f in result["findings"]:
            name = f.get("name", "Unknown")
            value = f.get("value", "")
            unit = f.get("unit", "")
            status = f.get("status", "")
            normal = f.get("normal_range", "")
            status_icon = (
                "✅" if status == "normal" else "⚠️" if status == "abnormal" else "🔍"
            )
            lines.append(
                f"- {status_icon} {name}: {value} {unit} (Normal: {normal}) — {status}"
            )
    if result.get("abnormal_flags"):
        lines.append(f"\n**Abnormal findings:** {', '.join(result['abnormal_flags'])}")
    if result.get("next_steps"):
        lines.append("\n**Next Steps:**")
        for step in result["next_steps"]:
            lines.append(f"- {step}")
    if result.get("disclaimer"):
        lines.append(f"\n*{result['disclaimer']}*")
    return "\n".join(lines) if lines else json.dumps(result, indent=2)
