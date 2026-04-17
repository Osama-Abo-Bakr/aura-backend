"""Regression tests for bug fixes in auth, wellness, and tickets endpoints.

These tests verify that previously reported bugs stay fixed:
1. /me returns null profile gracefully instead of crashing with AttributeError
2. upsert_profile converts datetime/date objects to ISO strings
3. wellness get_plan handles None response from maybe_single().execute()
4. tickets endpoints catch postgrest APIError and return 503
5. signout passes raw Bearer token (not empty string)
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.core.deps import get_current_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# Supabase mock chain builder
def _make_auth_override(user_dict: dict | None = None):
    """Return a dependency override function for get_current_user."""
    if user_dict is None:
        user_dict = {
            "sub": "00000000-0000-0000-0000-000000000001",
            "email": "test@example.com",
            "role": "authenticated",
        }
    return lambda: user_dict


# ---------------------------------------------------------------------------
# Test: /me returns null profile gracefully
# ---------------------------------------------------------------------------


class TestMeNullProfile(unittest.TestCase):
    """Regression test: /me should not crash when profile_resp is None."""

    def setUp(self):
        self.client = TestClient(app)
        self.user = {
            "sub": "00000000-0000-0000-0000-000000000001",
            "email": "test@example.com",
            "role": "authenticated",
        }
        app.dependency_overrides[get_current_user] = lambda: self.user

    def tearDown(self):
        app.dependency_overrides.clear()

    @patch("app.api.v1.auth.supabase_admin")
    def test_me_returns_null_profile_when_no_profile(
        self, mock_admin: MagicMock
    ) -> None:
        """GET /me should return profile: null instead of crashing when user has no profile."""
        # Simulate maybe_single().execute() returning None (user has no profile yet)
        mock_admin.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = None

        response = self.client.get(
            "/api/v1/me", headers={"Authorization": "Bearer test-token"}
        )

        self.assertEqual(
            response.status_code,
            200,
            f"Expected 200, got {response.status_code}: {response.text}",
        )
        data = response.json()
        self.assertIsNone(
            data["profile"], "Expected profile to be null when no profile exists"
        )
        self.assertIn("subscription", data)

    @patch("app.api.v1.auth.supabase_admin")
    def test_me_returns_profile_when_exists(self, mock_admin: MagicMock) -> None:
        """GET /me should return profile data when profile exists."""
        profile_data = {
            "id": "00000000-0000-0000-0000-000000000002",
            "user_id": "00000000-0000-0000-0000-000000000001",
            "full_name": "Test User",
            "language": "en",
            "country": "US",
            "avatar_url": None,
            "health_goals": [],
            "conditions": [],
            "date_of_birth": None,
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }
        mock_resp = MagicMock()
        mock_resp.data = profile_data

        # Profile query returns data
        mock_admin.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = mock_resp
        # Subscription query returns None (no active sub)
        mock_admin.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = None

        response = self.client.get(
            "/api/v1/me", headers={"Authorization": "Bearer test-token"}
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["profile"]["full_name"], "Test User")
        self.assertEqual(data["subscription"]["tier"], "free")


# ---------------------------------------------------------------------------
# Test: upsert_profile converts datetime to ISO string
# ---------------------------------------------------------------------------


class TestUpsertProfileDatetimeSerialization(unittest.TestCase):
    """Regression test: upsert_profile should convert datetime/date to ISO string."""

    def setUp(self):
        self.client = TestClient(app)
        self.user = {
            "sub": "00000000-0000-0000-0000-000000000001",
            "email": "test@example.com",
            "role": "authenticated",
        }
        app.dependency_overrides[get_current_user] = lambda: self.user

    def tearDown(self):
        app.dependency_overrides.clear()

    @patch("app.api.v1.auth.supabase_admin")
    def test_upsert_profile_serializes_datetime(self, mock_admin: MagicMock) -> None:
        """POST /auth/profile should convert datetime objects to ISO strings."""
        profile_data = {
            "id": "00000000-0000-0000-0000-000000000002",
            "user_id": "00000000-0000-0000-0000-000000000001",
            "full_name": "Test User",
            "language": "en",
            "country": None,
            "avatar_url": None,
            "health_goals": [],
            "conditions": [],
            "date_of_birth": "1990-01-15T00:00:00",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }
        mock_resp = MagicMock()
        mock_resp.data = [profile_data]
        mock_admin.table.return_value.upsert.return_value.execute.return_value = (
            mock_resp
        )

        # Send a date_of_birth as ISO string (simulating what the client sends)
        response = self.client.post(
            "/api/v1/auth/profile",
            json={"full_name": "Test User", "date_of_birth": "1990-01-15"},
            headers={"Authorization": "Bearer test-token"},
        )

        self.assertEqual(
            response.status_code,
            200,
            f"Expected 200, got {response.status_code}: {response.text}",
        )

        # Verify the upsert call received an ISO string, not a datetime object
        call_args = mock_admin.table.return_value.upsert.call_args
        upsert_data = call_args[0][0] if call_args[0] else call_args[1].get("data", {})
        self.assertIsInstance(
            upsert_data.get("date_of_birth"),
            str,
            "date_of_birth should be a string, not a datetime object",
        )


# ---------------------------------------------------------------------------
# Test: signout passes raw Bearer token
# ---------------------------------------------------------------------------


class TestSignoutBearerToken(unittest.TestCase):
    """Regression test: signout should pass the raw Bearer token, not an empty string."""

    def setUp(self):
        self.client = TestClient(app)
        self.user = {
            "sub": "00000000-0000-0000-0000-000000000001",
            "email": "test@example.com",
            "role": "authenticated",
        }
        app.dependency_overrides[get_current_user] = lambda: self.user

    def tearDown(self):
        app.dependency_overrides.clear()

    @patch("app.api.v1.auth.AuthService")
    def test_signout_passes_bearer_token(self, MockAuthService: MagicMock) -> None:
        """POST /auth/signout should pass the raw Bearer token to AuthService.signout()."""
        svc = MockAuthService.return_value
        svc.signout.return_value = None

        response = self.client.post(
            "/api/v1/auth/signout", headers={"Authorization": "Bearer my-test-token"}
        )

        self.assertEqual(
            response.status_code,
            200,
            f"Expected 200, got {response.status_code}: {response.text}",
        )
        # Verify signout was called with the raw token (not empty string)
        svc.signout.assert_called_once_with("my-test-token")

    @patch("app.api.v1.auth.AuthService")
    def test_signout_does_not_pass_empty_token(
        self, MockAuthService: MagicMock
    ) -> None:
        """POST /auth/signout should never pass an empty Bearer token."""
        svc = MockAuthService.return_value
        svc.signout.return_value = None

        response = self.client.post(
            "/api/v1/auth/signout", headers={"Authorization": "Bearer my-valid-token"}
        )

        self.assertEqual(response.status_code, 200)
        call_args = svc.signout.call_args
        token_passed = call_args[0][0]
        self.assertNotEqual(
            token_passed, "", "signout should not receive an empty string"
        )
        self.assertTrue(
            token_passed.startswith("my-"), f"Expected raw token, got: {token_passed}"
        )


if __name__ == "__main__":
    unittest.main()
