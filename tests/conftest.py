"""
Shared pytest fixtures and configuration.
"""

from __future__ import annotations

import os

import pytest

# ---------------------------------------------------------------------------
# Set minimal env vars before any app module is imported
# This prevents Settings() from blowing up with missing required fields.
# ---------------------------------------------------------------------------
# Use a valid-looking JWT for SUPABASE_SERVICE_ROLE_KEY — the Supabase client
# validates the key format at module import time, so a plain string like
# "test-service-role-key" causes SupabaseException("Invalid API key").
# This is a real Base64url-encoded JWT (3 dot-separated segments) that the
# create_client call will accept.
_TEST_SUPABASE_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJvbGUiOiJzZXJ2aWNlX3JvbGUiLCJpYXQiOjE2NjY"
    "5MDk4MDB9."
    "fake_signature_for_tests_XXXXXX"
)
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", _TEST_SUPABASE_KEY)
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-32chars-padding!!")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")


@pytest.fixture(scope="session", autouse=True)
def patch_genai_configure():
    """Prevent google.generativeai from making real API calls during tests."""
    import unittest.mock as mock

    with mock.patch("google.generativeai.configure"):
        yield
