"""Unit tests for Authentication & Authorization layer (Google IAP, Bearer, API Key)."""

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import unittest
from fastapi.testclient import TestClient

from backend.app.core.auth import (
    AuthenticatedUser,
    authenticate_request,
    extract_iap_user_email,
)
from backend.app.core.config import get_settings
from backend.app.main import app


class TestAuthLayer(unittest.TestCase):
    """Test suite for authentication middleware and identity extraction."""

    def setUp(self):
        self.client = TestClient(app)
        self.settings = get_settings()

    def test_extract_iap_user_email(self):
        """Verify extraction of user email from Google Cloud IAP header."""
        mock_req = MagicMock()
        mock_req.headers = {"X-Goog-Authenticated-User-Email": "accounts.google.com:dpo@example-tre.org"}
        email = extract_iap_user_email(mock_req)
        self.assertEqual(email, "dpo@example-tre.org")

        mock_req.headers = {"X-Goog-Authenticated-User-Email": "researcher@university.edu"}
        email = extract_iap_user_email(mock_req)
        self.assertEqual(email, "researcher@university.edu")

        mock_req.headers = {}
        email = extract_iap_user_email(mock_req)
        self.assertIsNone(email)

    def test_default_dev_bypass_allows_requests(self):
        """Verify when ENABLE_API_AUTH=False, requests pass without credentials."""
        self.settings.ENABLE_API_AUTH = False
        res = self.client.get("/api/v1/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "HEALTHY")

    def test_auth_enforced_blocks_unauthenticated(self):
        """Verify when ENABLE_API_AUTH=True, unauthenticated requests return 401."""
        self.settings.ENABLE_API_AUTH = True
        try:
            res = self.client.get("/api/v1/rooms")
            self.assertEqual(res.status_code, 401)
            self.assertIn("Authentication required", res.json()["detail"])
        finally:
            self.settings.ENABLE_API_AUTH = False

    def test_auth_enforced_allows_health_and_docs(self):
        """Verify public endpoints remain accessible even when ENABLE_API_AUTH=True."""
        self.settings.ENABLE_API_AUTH = True
        try:
            res = self.client.get("/api/v1/health")
            self.assertEqual(res.status_code, 200)
        finally:
            self.settings.ENABLE_API_AUTH = False

    def test_auth_enforced_accepts_iap_header(self):
        """Verify Google Cloud IAP header authenticates the request."""
        self.settings.ENABLE_API_AUTH = True
        try:
            headers = {"X-Goog-Authenticated-User-Email": "accounts.google.com:admin@example-tre.org"}
            res = self.client.get("/api/v1/rooms", headers=headers)
            self.assertNotEqual(res.status_code, 401)
        finally:
            self.settings.ENABLE_API_AUTH = False

    def test_auth_enforced_accepts_bearer_token(self):
        """Verify valid Bearer token authenticates the request."""
        self.settings.ENABLE_API_AUTH = True
        self.settings.API_AUTH_TOKEN = "secret-tre-token-123"
        try:
            headers = {"Authorization": "Bearer secret-tre-token-123"}
            res = self.client.get("/api/v1/rooms", headers=headers)
            self.assertNotEqual(res.status_code, 401)

            # Invalid token should be rejected with 401
            bad_headers = {"Authorization": "Bearer wrong-token"}
            bad_res = self.client.get("/api/v1/rooms", headers=bad_headers)
            self.assertEqual(bad_res.status_code, 401)
        finally:
            self.settings.ENABLE_API_AUTH = False
            self.settings.API_AUTH_TOKEN = None

    def test_auth_enforced_accepts_api_key(self):
        """Verify valid X-API-Key header authenticates the request."""
        self.settings.ENABLE_API_AUTH = True
        self.settings.API_AUTH_TOKEN = "tre-api-key-xyz"
        try:
            headers = {"X-API-Key": "tre-api-key-xyz"}
            res = self.client.get("/api/v1/rooms", headers=headers)
            self.assertNotEqual(res.status_code, 401)

            # Invalid key should be rejected with 401
            bad_headers = {"X-API-Key": "wrong-key"}
            bad_res = self.client.get("/api/v1/rooms", headers=bad_headers)
            self.assertEqual(bad_res.status_code, 401)
        finally:
            self.settings.ENABLE_API_AUTH = False
            self.settings.API_AUTH_TOKEN = None

    def test_auth_enforced_fails_closed_when_token_is_none(self):
        """Verify that when API_AUTH_TOKEN is None/unset, random tokens are rejected (fail closed)."""
        self.settings.ENABLE_API_AUTH = True
        self.settings.API_AUTH_TOKEN = None
        try:
            # Bearer token without valid OIDC or static token should be 401
            res_bearer = self.client.get("/api/v1/rooms", headers={"Authorization": "Bearer random-unvalidated-token"})
            self.assertEqual(res_bearer.status_code, 401)

            # API Key without static token should be 401
            res_key = self.client.get("/api/v1/rooms", headers={"X-API-Key": "random-key"})
            self.assertEqual(res_key.status_code, 401)
        finally:
            self.settings.ENABLE_API_AUTH = False


if __name__ == "__main__":
    unittest.main()
