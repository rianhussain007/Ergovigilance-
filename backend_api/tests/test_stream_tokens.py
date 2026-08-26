"""Tests for stream-scoped video tokens and MJPEG endpoint authentication.

Guarantees under test:
- Stream tokens are short-lived, purpose-bound ("stream"), and tamper-proof.
- An API JWT can NEVER be replayed as a stream token (and vice versa).
- The MJPEG feed rejects anonymous/garbage credentials with 401 — camera
  video must never be watchable without credentials.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

from app.core.database import init_local_database
from app.core.security import (
    AuthenticatedUser,
    create_access_token,
    create_stream_token,
    decode_access_token,
    verify_stream_token,
)

init_local_database()


class TestStreamTokenRoundTrip:
    def test_mint_and_verify(self):
        token = create_stream_token(7, "admin")
        payload = verify_stream_token(token)
        assert payload is not None
        assert payload["sub"] == "7"
        assert payload["role"] == "admin"
        assert payload["purpose"] == "stream"

    def test_tampered_body_rejected(self):
        token = create_stream_token(1, "operator")
        body, sig = token.split(".", 1)
        flipped = body[:-2] + ("AA" if not body.endswith("AA") else "BB")
        assert verify_stream_token(f"{flipped}.{sig}") is None

    def test_tampered_signature_rejected(self):
        token = create_stream_token(1, "operator")
        body, sig = token.split(".", 1)
        bad_sig = sig[:-2] + ("AA" if not sig.endswith("AA") else "BB")
        assert verify_stream_token(f"{body}.{bad_sig}") is None

    def test_expired_token_rejected(self):
        from app.core import security

        now = int(time.time()) - security.STREAM_TOKEN_TTL_SECONDS - 10
        payload = {
            "sub": "1",
            "role": "operator",
            "purpose": "stream",
            "iat": now,
            "exp": now + 60,
        }
        body = security._b64url_encode(json.dumps(payload).encode("utf-8"))
        digest = hmac.new(
            security.JWT_SECRET.encode("utf-8"),
            b"stream." + body.encode("ascii"),
            hashlib.sha256,
        ).digest()
        expired = f"{body}.{security._b64url_encode(digest)}"
        assert verify_stream_token(expired) is None


class TestTokenScopeSeparation:
    def test_api_jwt_is_not_a_stream_token(self):
        user = AuthenticatedUser(id=3, email="op@example.local", role="operator")
        api_jwt = create_access_token(user)
        # Valid as an API credential...
        assert decode_access_token(api_jwt)["sub"] == "3"
        # ...but worthless against the stream endpoint's scoped check.
        assert verify_stream_token(api_jwt) is None

    def test_stream_token_cannot_authenticate_the_api(self):
        stream_token = create_stream_token(3, "operator")
        with pytest.raises(ValueError):
            decode_access_token(stream_token)


@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


class TestVideoFeedAuthEnforcement:
    def test_anonymous_request_rejected_with_401(self, client: TestClient):
        res = client.get("/video/feed")
        assert res.status_code == 401

    def test_garbage_query_token_rejected_with_401(self, client: TestClient):
        res = client.get("/video/feed?token=garbage")
        assert res.status_code == 401

    def test_expired_stream_token_rejected_with_401(self, client: TestClient):
        from app.core import security

        now = int(time.time()) - security.STREAM_TOKEN_TTL_SECONDS - 10
        payload = {"sub": "1", "role": "admin", "purpose": "stream", "iat": now, "exp": now + 60}
        body = security._b64url_encode(json.dumps(payload).encode("utf-8"))
        digest = hmac.new(
            security.JWT_SECRET.encode("utf-8"),
            b"stream." + body.encode("ascii"),
            hashlib.sha256,
        ).digest()
        res = client.get(f"/video/feed?stream_token={body}.{security._b64url_encode(digest)}")
        assert res.status_code == 401

    def test_valid_stream_token_passes_auth_layer(self, client: TestClient):
        """A VALID stream token gets past authentication — it may then receive
        a 503 (no live service in the test env), but never a 401."""
        from app.core.security import JWT_SECRET  # resolved per-process

        token = create_stream_token(1, "admin")
        res = client.get(f"/video/feed?stream_token={token}")
        assert res.status_code != 401
