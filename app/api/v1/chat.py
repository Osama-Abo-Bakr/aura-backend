"""
Chat endpoints — Week 4 implementation.

Routes:
  POST   /api/v1/chat/message                              — stream a health Q&A response
  GET    /api/v1/chat/conversations                        — list user's conversations
  GET    /api/v1/chat/conversations/{conversation_id}/messages — messages in a conversation
  DELETE /api/v1/chat/conversations/{conversation_id}      — delete a conversation
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.deps import get_current_user, make_quota_checker
from app.db.supabase import supabase_admin
from app.services.gemini import FLASH_MODEL, stream_chat_response

router = APIRouter(prefix="/chat")


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ChatMessageRequest(BaseModel):
    content: str = Field(..., min_length=1)
    conversation_id: str | None = None
    language: str = "en"


# ---------------------------------------------------------------------------
# POST /chat/message
# ---------------------------------------------------------------------------


@router.post(
    "/message",
    summary="Stream a health Q&A response via SSE",
    dependencies=[Depends(make_quota_checker("chat"))],
)
async def send_chat_message(
    body: ChatMessageRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> StreamingResponse:
    """
    Send a user message and receive an SSE-streamed assistant response.

    - Creates a new conversation if ``conversation_id`` is not supplied.
    - Persists the user message before streaming.
    - Persists the full assistant reply after the stream completes.
    - Records a quota interaction row in ``ai_interactions``.
    """
    user_id: str = current_user["sub"]
    conversation_id: str = body.conversation_id or ""
    language: str = body.language

    # ------------------------------------------------------------------
    # 1. Resolve / create conversation
    # ------------------------------------------------------------------
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
        title = body.content[:50]
        supabase_admin.table("conversations").insert(
            {
                "id": conversation_id,
                "user_id": user_id,
                "language": language if language in ("ar", "en") else "en",
                "title": title,
            }
        ).execute()
    else:
        # Verify the conversation belongs to the current user.
        conv_resp = (
            supabase_admin.table("conversations")
            .select("id, user_id")
            .eq("id", conversation_id)
            .maybe_single()
            .execute()
        )
        if not conv_resp.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "conversation_not_found"},
            )
        if conv_resp.data["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "conversation_not_owned"},
            )

    # ------------------------------------------------------------------
    # 2. Persist user message
    # ------------------------------------------------------------------
    supabase_admin.table("messages").insert(
        {
            "id": str(uuid.uuid4()),
            "conversation_id": conversation_id,
            "user_id": user_id,
            "role": "user",
            "content": body.content,
        }
    ).execute()

    # ------------------------------------------------------------------
    # 3. Fetch last 10 messages for context (ASC order)
    # ------------------------------------------------------------------
    history_resp = (
        supabase_admin.table("messages")
        .select("role, content")
        .eq("conversation_id", conversation_id)
        .order("created_at", desc=False)
        .limit(10)
        .execute()
    )
    message_history: list[dict] = [
        {"role": row["role"], "content": row["content"]}
        for row in (history_resp.data or [])
    ]

    # ------------------------------------------------------------------
    # 4. Record quota interaction
    # ------------------------------------------------------------------
    supabase_admin.table("ai_interactions").insert(
        {
            "user_id": user_id,
            "interaction_type": "chat",
            "model_used": FLASH_MODEL,
        }
    ).execute()

    # ------------------------------------------------------------------
    # 5. Stream response via SSE
    # ------------------------------------------------------------------
    async def event_generator():
        full_response = ""
        async for chunk in stream_chat_response(message_history, language):
            full_response += chunk
            # Escape newlines so each SSE data line is on a single line.
            safe_chunk = chunk.replace("\n", "\\n")
            yield f"data: {safe_chunk}\n\n"

        # 6. Save full assistant response to DB after streaming completes.
        supabase_admin.table("messages").insert(
            {
                "id": str(uuid.uuid4()),
                "conversation_id": conversation_id,
                "user_id": user_id,
                "role": "assistant",
                "content": full_response,
            }
        ).execute()

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ---------------------------------------------------------------------------
# GET /chat/conversations
# ---------------------------------------------------------------------------


@router.get(
    "/conversations",
    status_code=status.HTTP_200_OK,
    summary="List the authenticated user's conversations",
)
async def list_conversations(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[dict]:
    """
    Return up to 20 most recent conversations for the authenticated user,
    each annotated with a ``message_count`` field.
    """
    user_id: str = current_user["sub"]

    convs_resp = (
        supabase_admin.table("conversations")
        .select("id, title, language, created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )

    conversations = convs_resp.data or []

    # Annotate each conversation with its message count.
    result = []
    for conv in conversations:
        count_resp = (
            supabase_admin.table("messages")
            .select("id", count="exact")
            .eq("conversation_id", conv["id"])
            .execute()
        )
        result.append(
            {
                "id": conv["id"],
                "title": conv["title"],
                "language": conv["language"],
                "created_at": conv["created_at"],
                "message_count": count_resp.count or 0,
            }
        )

    return result


# ---------------------------------------------------------------------------
# GET /chat/conversations/{conversation_id}/messages
# ---------------------------------------------------------------------------


@router.get(
    "/conversations/{conversation_id}/messages",
    status_code=status.HTTP_200_OK,
    summary="Fetch all messages in a conversation",
)
async def get_conversation_messages(
    conversation_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[dict]:
    """
    Return all messages in the given conversation, ordered oldest-first.
    Returns 404 if the conversation does not exist or belongs to another user.
    """
    user_id: str = current_user["sub"]

    # Verify ownership.
    conv_resp = (
        supabase_admin.table("conversations")
        .select("id, user_id")
        .eq("id", conversation_id)
        .maybe_single()
        .execute()
    )
    if not conv_resp.data or conv_resp.data["user_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "conversation_not_found"},
        )

    msgs_resp = (
        supabase_admin.table("messages")
        .select("id, role, content, created_at")
        .eq("conversation_id", conversation_id)
        .order("created_at", desc=False)
        .execute()
    )

    return [
        {
            "id": row["id"],
            "role": row["role"],
            "content": row["content"],
            "created_at": row["created_at"],
        }
        for row in (msgs_resp.data or [])
    ]


# ---------------------------------------------------------------------------
# DELETE /chat/conversations/{conversation_id}
# ---------------------------------------------------------------------------


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a conversation and all its messages",
)
async def delete_conversation(
    conversation_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict:
    """
    Delete the specified conversation (cascades to messages via FK).
    Returns 404 if the conversation does not exist or belongs to another user.
    """
    user_id: str = current_user["sub"]

    # Verify ownership.
    conv_resp = (
        supabase_admin.table("conversations")
        .select("id, user_id")
        .eq("id", conversation_id)
        .maybe_single()
        .execute()
    )
    if not conv_resp.data or conv_resp.data["user_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "conversation_not_found"},
        )

    supabase_admin.table("conversations").delete().eq("id", conversation_id).execute()

    return {"deleted": True}
