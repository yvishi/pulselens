"""Customer tokens and the agent passcode (docs/CONTRACT.md section 2).

The token secret is random per server start and kept in memory: a restart invalidates open sessions, which is fine
for the demo. Every comparison is constant-time.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets


class TokenSigner:
    def __init__(self, secret: bytes | None = None) -> None:
        self._secret = secret or secrets.token_bytes(32)

    def customer_token(self, session_id: str) -> str:
        return hmac.new(self._secret, session_id.encode(), hashlib.sha256).hexdigest()[:32]

    def check(self, session_id: str, token: str | None) -> bool:
        return bool(token) and hmac.compare_digest(self.customer_token(session_id), str(token))


def bearer(header: str | None) -> str | None:
    """The token from `Authorization: Bearer <token>`, or None."""
    if not header:
        return None
    scheme, _, token = header.partition(" ")
    return token.strip() or None if scheme.lower() == "bearer" else None


def passcode_ok(given: str | None, expected: str) -> bool:
    return bool(given) and hmac.compare_digest(str(given).encode(), expected.encode())
