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
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-32chars-padding!!")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")


@pytest.fixture(scope="session", autouse=True)
def patch_genai_configure():
    """Prevent google.generativeai from making real API calls during tests."""
    import unittest.mock as mock

    with mock.patch("google.generativeai.configure"):
        yield
