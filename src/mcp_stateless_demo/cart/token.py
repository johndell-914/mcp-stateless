"""The explicit handle: a signed, opaque ``cart_token``.

This is the heart of the stateless design. Instead of the server remembering
which cart belongs to a session, the *client* carries an opaque token as a tool
argument. The token is an HMAC-signed reference to a cart id, so a client cannot
forge or tamper with an id it was never given. Kept deliberately small — it is
shown on stage.
"""

from __future__ import annotations

import base64
import hashlib
import hmac


class InvalidToken(Exception):
    """A cart_token was malformed or failed signature verification."""


class CartTokenCodec:
    """Encode/verify ``cart_token`` handles with an HMAC-SHA256 signature."""

    def __init__(self, secret: str) -> None:
        if not secret:
            raise ValueError("token secret must not be empty")
        self._key = secret.encode("utf-8")

    def encode(self, cart_id: str) -> str:
        return f"{cart_id}.{self._sign(cart_id)}"

    def decode(self, token: str) -> str:
        try:
            cart_id, signature = token.rsplit(".", 1)
        except ValueError as exc:
            raise InvalidToken("malformed token") from exc
        if not hmac.compare_digest(signature, self._sign(cart_id)):
            raise InvalidToken("bad signature")
        return cart_id

    def _sign(self, cart_id: str) -> str:
        digest = hmac.new(self._key, cart_id.encode("utf-8"), hashlib.sha256).digest()
        return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
