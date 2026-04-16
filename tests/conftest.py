"""
Shared pytest fixtures and configuration.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Set minimal env vars before any app module is imported.
# This prevents Settings() from blowing up with missing required fields.
# ---------------------------------------------------------------------------
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-32chars-padding!!")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")

# ---------------------------------------------------------------------------
# Patch supabase.create_client at module level (before any app module is
# imported) so that supabase_admin in app.db.supabase is a MagicMock instead
# of trying to connect to a real Supabase instance.  This must happen here
# because module-level code in app.db.supabase runs at import time.
# ---------------------------------------------------------------------------
_mock_supabase_client = MagicMock()

import supabase as _supabase_mod  # noqa: E402

_original_create_client = _supabase_mod.create_client
_supabase_mod.create_client = lambda *a, **kw: _mock_supabase_client

# Pre-import app.db.supabase so it picks up the patched create_client.
import app.db.supabase  # noqa: E402, F401


@pytest.fixture(scope="session", autouse=True)
def _patch_genai_configure():
    """Prevent google.generativeai from making real API calls during tests."""
    import unittest.mock as mock

    with mock.patch("google.generativeai.configure"):
        yield


@pytest.fixture(autouse=True)
def _reset_mock_supabase():
    """Reset the mock supabase client between tests so state doesn't leak."""
    _mock_supabase_client.reset_mock()
    # Re-chain the builder pattern after reset
    _mock_supabase_client.table.return_value = _mock_supabase_client
    _mock_supabase_client.select.return_value = _mock_supabase_client
    _mock_supabase_client.insert.return_value = _mock_supabase_client
    _mock_supabase_client.update.return_value = _mock_supabase_client
    _mock_supabase_client.delete.return_value = _mock_supabase_client
    _mock_supabase_client.eq.return_value = _mock_supabase_client
    _mock_supabase_client.maybe_single.return_value = _mock_supabase_client
    _mock_supabase_client.order.return_value = _mock_supabase_client
    _mock_supabase_client.upsert.return_value = _mock_supabase_client
    yield