"""Unified chat endpoint that handles text messages, skin images, and report files
through a LangGraph state machine with SSE streaming."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.core.deps import check_quota, get_current_user
from app.db.supabase import supabase_admin
from app.graph import ConversationState, FileAttachment, conversation_graph
from app.models.chat import (
    AnalysisErrorEvent,
    AnalysisMetaEvent,
    ChatMessageRequest,
    ContentEvent,
    QuotaErrorEvent,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])


def _determine_quota_type(request: ChatMessageRequest) -> str:
    """Return the interaction type for quota checking."""
    if not request.has_file():
        return "chat"
    category = request.get_file_type_category()
    if category == "image":
        return "skin"
    if category == "pdf":
        return "report"
    return "chat"


@router.post("/message")
async def send_message(
    request: ChatMessageRequest,
    user: dict = Depends(get_current_user),
):
    """Send a message with optional file attachment. Streams SSE response."""
    user_id = user["sub"]

    # Determine quota type and check
    quota_type = _determine_quota_type(request)
    try:
        await check_quota(quota_type, user)
    except HTTPException:
        event = QuotaErrorEvent(
            message=f"You've used all your {quota_type} credits this month.",
            interaction_type=quota_type,
        )

        async def quota_error_stream():
            yield f"data: {event.model_dump_json()}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(quota_error_stream(), media_type="text/event-stream")

    # Get or create conversation
    conversation_id = str(request.conversation_id) if request.conversation_id else None
    if conversation_id:
        conv_resp = (
            supabase_admin.table("conversations")
            .select("id")
            .eq("id", conversation_id)
            .eq("user_id", user_id)
            .execute()
        )
        if not conv_resp.data:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        title = request.content[:50] if request.content else "New Conversation"
        conv_resp = (
            supabase_admin.table("conversations")
            .insert({"user_id": user_id, "language": request.language, "title": title})
            .execute()
        )
        conversation_id = conv_resp.data[0]["id"]

    # Save user message to DB
    msg_data = {
        "id": str(uuid4()),
        "conversation_id": conversation_id,
        "user_id": user_id,
        "role": "user",
        "content": request.content,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if request.file_path:
        msg_data["file_path"] = request.file_path
        msg_data["file_type"] = request.file_type

    supabase_admin.table("messages").insert(msg_data).execute()

    # Load conversation history (last 20 messages)
    messages_resp = (
        supabase_admin.table("messages")
        .select("role, content")
        .eq("conversation_id", conversation_id)
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )
    messages = list(reversed(messages_resp.data)) if messages_resp.data else []

    # Build file attachment if present
    current_file = None
    if request.file_path and request.file_type:
        current_file = FileAttachment(
            file_path=request.file_path, file_type=request.file_type
        )

    # Build initial state
    initial_state = ConversationState(
        user_id=user_id,
        conversation_id=conversation_id,
        language=request.language,
        current_message=request.content,
        current_file=current_file,
        messages=messages,
        last_analysis=None,
        last_analysis_type=None,
        summary_context="",
        response_chunks=[],
        analysis_meta=None,
        error=None,
    )

    # Run the graph
    async def stream_response():
        try:
            result = await conversation_graph.ainvoke(initial_state)

            # Stream content chunks
            for chunk in result.get("response_chunks", []):
                event = ContentEvent(text=chunk)
                yield f"data: {event.model_dump_json()}\n\n"

            # Stream analysis meta if present
            analysis_meta = result.get("analysis_meta")
            if analysis_meta:
                event = AnalysisMetaEvent(
                    analysis_type=analysis_meta["analysis_type"],
                    analysis_id=analysis_meta["analysis_id"],
                )
                yield f"data: {event.model_dump_json()}\n\n"

            # Stream error if present
            if result.get("error"):
                event = AnalysisErrorEvent(message=result["error"])
                yield f"data: {event.model_dump_json()}\n\n"

            # Save assistant message to DB
            full_response = "".join(result.get("response_chunks", []))
            assistant_msg_data = {
                "id": str(uuid4()),
                "conversation_id": conversation_id,
                "user_id": user_id,
                "role": "assistant",
                "content": full_response,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            if analysis_meta:
                assistant_msg_data["analysis_id"] = analysis_meta["analysis_id"]

            supabase_admin.table("messages").insert(assistant_msg_data).execute()

            # Record quota usage
            interaction_type = "chat"
            if current_file and current_file.get("file_type", "").startswith("image/"):
                interaction_type = "skin"
            elif current_file and current_file.get("file_type") == "application/pdf":
                interaction_type = "report"
            supabase_admin.table("ai_interactions").insert(
                {
                    "user_id": user_id,
                    "interaction_type": interaction_type,
                }
            ).execute()

        except Exception as e:
            logger.error(f"Chat graph error: {e}", exc_info=True)
            error_event = AnalysisErrorEvent(
                message="An unexpected error occurred. Please try again."
            )
            yield f"data: {error_event.model_dump_json()}\n\n"

        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(stream_response(), media_type="text/event-stream")


@router.get("/conversations", response_model=list[dict])
async def list_conversations(user: dict = Depends(get_current_user)):
    """List user's most recent conversations."""
    user_id = user["sub"]
    resp = (
        supabase_admin.table("conversations")
        .select("id, title, created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )
    return resp.data


@router.get("/conversations/{conversation_id}/messages", response_model=list[dict])
async def get_messages(conversation_id: str, user: dict = Depends(get_current_user)):
    """Get all messages in a conversation."""
    user_id = user["sub"]
    conv_resp = (
        supabase_admin.table("conversations")
        .select("id")
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not conv_resp.data:
        raise HTTPException(status_code=404, detail="Conversation not found")

    try:
        resp = (
            supabase_admin.table("messages")
            .select("id, role, content, created_at, file_path, file_type, analysis_id")
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=False)
            .execute()
        )
    except Exception:
        # Fallback: migration 005 may not be applied yet
        resp = (
            supabase_admin.table("messages")
            .select("id, role, content, created_at")
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=False)
            .execute()
        )
    return resp.data


@router.get("/conversations/{conversation_id}/analysis")
async def get_conversation_analysis(
    conversation_id: str,
    user: dict = Depends(get_current_user),
):
    """Get the latest analysis result in a conversation."""
    user_id = user["sub"]

    # Find messages with analysis_id in this conversation
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
        raise HTTPException(
            status_code=404, detail="No analysis found in this conversation"
        )

    analysis_id = msgs_resp.data[0]["analysis_id"]

    # Fetch the analysis
    analysis_resp = (
        supabase_admin.table("analyses").select("*").eq("id", analysis_id).execute()
    )

    if not analysis_resp.data:
        raise HTTPException(status_code=404, detail="Analysis not found")

    return analysis_resp.data[0]


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str, user: dict = Depends(get_current_user)
):
    """Delete a conversation and all its messages."""
    user_id = user["sub"]

    conv_resp = (
        supabase_admin.table("conversations")
        .select("id")
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not conv_resp.data:
        raise HTTPException(status_code=404, detail="Conversation not found")

    supabase_admin.table("messages").delete().eq(
        "conversation_id", conversation_id
    ).execute()
    supabase_admin.table("conversations").delete().eq("id", conversation_id).execute()

    return {"status": "deleted"}
