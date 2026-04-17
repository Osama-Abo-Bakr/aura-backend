"""
Supabase Storage service layer.

Week 2: real implementations of upload URL generation and file download.
"""

from __future__ import annotations

import mimetypes
import uuid

import httpx

from app.db.supabase import supabase_admin

# Ensure mimetypes has common mappings initialised
mimetypes.init()

BUCKET = "analyses"


def generate_upload_url(user_id: str, file_name: str, content_type: str) -> dict:
    """
    Generate a signed Supabase Storage upload URL (30-minute expiry).

    Args:
        user_id: The authenticated user's UUID (used as path prefix).
        file_name: Original file name provided by the client.
        content_type: MIME type of the file (e.g. 'image/jpeg').

    Returns:
        {
            "upload_url": "<signed PUT URL>",
            "file_path": "<user_id>/<uuid>_<file_name>",
        }
    """
    safe_name = f"{uuid.uuid4()}_{file_name}"
    path = f"{user_id}/{safe_name}"
    response = supabase_admin.storage.from_(BUCKET).create_signed_upload_url(path)
    # supabase-py may return either {"signedURL": ...} or {"signed_url": ...}
    # depending on the client version — handle both shapes.
    upload_url = (
        response.get("signedURL")
        or response.get("signed_url")
        or response.get("url", "")
    )
    return {
        "upload_url": upload_url,
        "file_path": path,
    }


async def download_file(file_path: str) -> tuple[bytes, str]:
    """
    Download a file from Supabase Storage using a short-lived signed URL.

    Args:
        file_path: Path of the file inside the bucket (no bucket prefix).

    Returns:
        Tuple of (raw_bytes, mime_type).
    """
    signed = supabase_admin.storage.from_(BUCKET).create_signed_url(
        file_path, expires_in=300
    )
    # Handle both dict shapes from different supabase-py releases.
    url = signed.get("signedURL") or signed.get("signed_url") or signed.get("url", "")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        # Determine MIME type: prefer Content-Type header, fall back to extension.
        content_type = resp.headers.get("content-type", "").split(";")[0].strip()
        if not content_type or content_type == "application/octet-stream":
            guessed, _ = mimetypes.guess_type(file_path)
            content_type = guessed or "application/octet-stream"
        return resp.content, content_type
