"""Hourly access code, so a public deployment cannot be used to spend the LLM key.

The code is derived, not stored: HMAC(ADMIN_TOKEN, current UTC hour). It changes on the hour
and nobody can compute it without ADMIN_TOKEN. The owner "requests" it by running
`python -m app.access` on the server (`docker compose exec api python -m app.access`) and
passes it on. A visitor trades the code for a session token that lasts one hour. Tokens are
signed, so nothing is stored.
"""

import base64
import hashlib
import hmac
import sys
import time

from fastapi import HTTPException

from app.config import get_settings

WINDOW = 3600  # the code changes on the hour
SESSION_TTL = 3600
MIN_TOKEN_LEN = 16


def check_config() -> None:
    t = get_settings().admin_token
    if t and len(t) < MIN_TOKEN_LEN:
        raise RuntimeError(f"ADMIN_TOKEN must be at least {MIN_TOKEN_LEN} characters.")


def _mac(msg: str) -> bytes:
    return hmac.new(get_settings().admin_token.encode(), msg.encode(), hashlib.sha256).digest()


def code_for(window: int) -> str:
    """Eight characters (40 bits) from the HMAC, shown as XXXX-XXXX."""
    raw = base64.b32encode(_mac(f"code:{window}")[:5]).decode()
    return f"{raw[:4]}-{raw[4:]}"


def current_window(now: float | None = None) -> int:
    return int((now if now is not None else time.time()) // WINDOW)


def verify_code(code: str, now: float | None = None) -> bool:
    given = code.strip().upper().replace("-", "").replace(" ", "")
    want = code_for(current_window(now)).replace("-", "")
    return hmac.compare_digest(given.encode(), want.encode())


def issue_session(now: float | None = None) -> tuple[str, int]:
    exp = int((now if now is not None else time.time()) + SESSION_TTL)
    return f"{exp}.{_mac(f'sess:{exp}').hex()[:32]}", exp


def verify_session(token: str, now: float | None = None) -> bool:
    exp, _, sig = token.partition(".")
    if not exp.isdigit():
        return False
    ok = hmac.compare_digest(sig.encode(), _mac(f"sess:{exp}").hex()[:32].encode())
    return ok and int(exp) > (now if now is not None else time.time())


def require_session(authorization: str | None) -> None:
    """Raise 401 unless `Authorization: Bearer <session token>` is valid. No-op when auth is off."""
    if not get_settings().admin_token:
        return
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not verify_session(token.strip()):
        raise HTTPException(401, "An access code is required. Codes change every hour.")


if __name__ == "__main__":
    if not get_settings().admin_token:
        sys.exit("ADMIN_TOKEN is not set, so access codes are off.")
    check_config()
    w = current_window() + (1 if "--next" in sys.argv else 0)
    left = (w + 1) * WINDOW - time.time() if w == current_window() else None
    until = time.strftime("%H:%M UTC", time.gmtime((w + 1) * WINDOW))
    print(code_for(w))
    print(f"valid until {until}" + (f" ({int(left // 60)} min left)" if left else " (next hour)"))
