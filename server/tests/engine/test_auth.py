"""engine/auth.py: bearer parsing, tokens and the passcode."""

from __future__ import annotations

import pytest

from pulselens.engine.auth import TokenSigner, bearer, passcode_ok


@pytest.mark.parametrize(("header", "token"), [
    ("Bearer abc", "abc"), ("bearer abc", "abc"), ("Bearer   abc  ", "abc"),
    ("Bearer", None), ("Bearer  ", None), ("Basic abc", None), ("", None), (None, None), ("abc", None),
])
def test_bearer(header: str | None, token: str | None) -> None:
    assert bearer(header) == token


def test_token_is_per_session_and_per_secret() -> None:
    a, b = TokenSigner(b"x" * 32), TokenSigner(b"y" * 32)
    assert len(a.customer_token("s1")) == 32
    assert a.check("s1", a.customer_token("s1"))
    assert not a.check("s2", a.customer_token("s1")) and not b.check("s1", a.customer_token("s1"))
    assert not a.check("s1", None) and not a.check("s1", "")


def test_passcode() -> None:
    assert passcode_ok("pc", "pc") and not passcode_ok("pd", "pc") and not passcode_ok(None, "pc")
