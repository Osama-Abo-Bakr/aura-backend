"""
Supabase Storage service layer.

Week 1: function signatures and type contracts only.
Full implementations ship in Week 2.
"""

from __future__ import annotations


async def generate_upload_url(
    bucket: str,
    file_path: str,
    expires_in: int = 300,
) -> dict[str, str]:
    """
    Generate a short-lived signed URL that the client can use to PUT a file
    directly into Supabase Storage without routing through the backend.

    Args:
        bucket: Storage bucket name (e.g. 'skin-images', 'medical-reports').
        file_path: Destination path inside the bucket, including file name.
        expires_in: URL validity in seconds (default 5 minutes).

    Returns:
        {
            "upload_url": "<signed PUT URL>",
            "file_path": "<bucket/file_path>",
            "expires_in": <seconds>
        }
    """
    raise NotImplementedError("generate_upload_url will be implemented in Week 2.")


async def download_file(
    bucket: str,
    file_path: str,
) -> bytes:
    """
    Download a file from Supabase Storage and return its raw bytes.

    Intended for server-side access (e.g. before passing an image to Gemini Vision).

    Args:
        bucket: Storage bucket name.
        file_path: Path of the file inside the bucket.

    Returns:
        Raw file bytes.
    """
    raise NotImplementedError("download_file will be implemented in Week 2.")
