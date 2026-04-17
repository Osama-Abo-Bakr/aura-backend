"""Tests for the auth service layer."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from app.services.auth import (
    AuthService,
    AuthTokens,
    DuplicateEmailError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    AuthServiceError,
)


class TestAuthService(unittest.TestCase):
    """Tests for AuthService using mocked httpx.Client."""

    def _mock_client(self, status_code: int, json_data: dict | str) -> MagicMock:
        """Build a mock httpx.Response with given status and JSON body."""
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        if isinstance(json_data, str):
            mock_resp.json.return_value = {"msg": json_data}
        else:
            mock_resp.json.return_value = json_data
        return mock_resp

    @patch("httpx.Client")
    def test_signup_calls_correct_endpoint(self, MockClient: MagicMock) -> None:
        """signup() POSTs to /auth/v1/signup with email, password, and full_name."""
        mock_resp = self._mock_client(200, {"id": "user_123"})
        MockClient.return_value.post.return_value = mock_resp

        svc = AuthService()
        result = svc.signup("alice@example.com", "secret123", "Alice Smith")

        call_args = MockClient.return_value.post.call_args
        self.assertTrue(
            call_args[0][0].endswith("/auth/v1/signup"),
            f"Expected URL ending with /auth/v1/signup, got {call_args[0][0]}",
        )
        payload = call_args[1]["json"]
        self.assertEqual(payload["email"], "alice@example.com")
        self.assertEqual(payload["password"], "secret123")
        self.assertEqual(payload["data"]["full_name"], "Alice Smith")
        self.assertEqual(result["id"], "user_123")

    @patch("httpx.Client")
    def test_signup_duplicate_email_raises(self, MockClient: MagicMock) -> None:
        """signup() with an already-registered email raises DuplicateEmailError."""
        mock_resp = self._mock_client(400, "Email already registered")
        MockClient.return_value.post.return_value = mock_resp

        svc = AuthService()
        with self.assertRaises(DuplicateEmailError) as ctx:
            svc.signup("alice@example.com", "secret123", "Alice Smith")
        self.assertIn("Email already registered", ctx.exception.detail)

    @patch("httpx.Client")
    def test_signin_calls_correct_endpoint(self, MockClient: MagicMock) -> None:
        """signin() POSTs to /auth/v1/token?grant_type=password."""
        mock_resp = self._mock_client(
            200,
            {
                "access_token": "tok_abc",
                "refresh_token": "ref_xyz",
                "expires_in": 3600,
            },
        )
        MockClient.return_value.post.return_value = mock_resp

        svc = AuthService()
        tokens = svc.signin("alice@example.com", "secret123")

        call_args = MockClient.return_value.post.call_args
        self.assertTrue(
            call_args[0][0].endswith("/auth/v1/token?grant_type=password"),
            f"Expected URL ending with /auth/v1/token?grant_type=password, got {call_args[0][0]}",
        )
        payload = call_args[1]["json"]
        self.assertEqual(payload["email"], "alice@example.com")
        self.assertEqual(payload["password"], "secret123")

        self.assertIsInstance(tokens, AuthTokens)
        self.assertEqual(tokens.access_token, "tok_abc")
        self.assertEqual(tokens.refresh_token, "ref_xyz")
        self.assertEqual(tokens.expires_in, 3600)
        self.assertEqual(tokens.token_type, "bearer")

    @patch("httpx.Client")
    def test_signin_wrong_password_raises(self, MockClient: MagicMock) -> None:
        """signin() with wrong credentials raises InvalidCredentialsError."""
        mock_resp = self._mock_client(400, "Invalid login credentials")
        MockClient.return_value.post.return_value = mock_resp

        svc = AuthService()
        with self.assertRaises(InvalidCredentialsError):
            svc.signin("alice@example.com", "wrongpassword")

    @patch("httpx.Client")
    def test_refresh_token_success(self, MockClient: MagicMock) -> None:
        """refresh_token() exchanges a refresh token for new tokens."""
        mock_resp = self._mock_client(
            200,
            {
                "access_token": "new_access",
                "refresh_token": "new_refresh",
                "expires_in": 3600,
            },
        )
        MockClient.return_value.post.return_value = mock_resp

        svc = AuthService()
        tokens = svc.refresh_token("old_refresh_token")

        self.assertIsInstance(tokens, AuthTokens)
        self.assertEqual(tokens.access_token, "new_access")
        self.assertEqual(tokens.refresh_token, "new_refresh")
        self.assertEqual(tokens.expires_in, 3600)

    @patch("httpx.Client")
    def test_refresh_token_invalid_raises(self, MockClient: MagicMock) -> None:
        """refresh_token() with an invalid token raises InvalidRefreshTokenError."""
        mock_resp = self._mock_client(401, "Invalid refresh token")
        MockClient.return_value.post.return_value = mock_resp

        svc = AuthService()
        with self.assertRaises(InvalidRefreshTokenError):
            svc.refresh_token("bad_token")

    @patch("httpx.Client")
    def test_signout_posts_to_logout(self, MockClient: MagicMock) -> None:
        """signout() posts to /auth/v1/logout with the access token."""
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        MockClient.return_value.post.return_value = mock_resp

        svc = AuthService()
        svc.signout("test_access_token")

        call_args = MockClient.return_value.post.call_args
        self.assertIn("/auth/v1/logout", call_args[0][0])

    @patch("httpx.Client")
    def test_client_has_timeout(self, MockClient: MagicMock) -> None:
        """AuthService sets a 10-second timeout on the httpx client."""
        AuthService()
        MockClient.assert_called_once_with(timeout=10.0)

    @patch("httpx.Client")
    def test_post_retries_on_transport_error(self, MockClient: MagicMock) -> None:
        """_post() retries on httpx.TransportError."""
        from httpx import TransportError

        MockClient.return_value.post.side_effect = TransportError("Connection reset")
        svc = AuthService()
        try:
            svc._post("/test", {})
        except AuthServiceError:
            pass  # _post converts TransportError to AuthServiceError after retries exhaust
        # tenacity should have called post 3 times (initial + 2 retries)
        self.assertEqual(MockClient.return_value.post.call_count, 3)

    @patch("httpx.Client")
    def test_post_does_not_retry_on_http_error(self, MockClient: MagicMock) -> None:
        """_post() does NOT retry on HTTP status errors (only TransportError)."""
        mock_resp = self._mock_client(400, "Bad request")
        MockClient.return_value.post.return_value = mock_resp
        svc = AuthService()
        resp = svc._post("/test", {})
        self.assertEqual(resp.status_code, 400)
        # Should only be called once — no retry
        self.assertEqual(MockClient.return_value.post.call_count, 1)


if __name__ == "__main__":
    unittest.main()
