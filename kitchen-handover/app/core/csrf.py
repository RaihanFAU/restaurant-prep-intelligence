"""Double-submit-cookie CSRF protection — no server-side state, no extra
dependency.

How it works: an HttpOnly `csrf_token` cookie holds a random value only the
server can set. Every state-changing request must echo that exact value
back, either as a hidden form field (`csrf_token`, traditional POSTs) or an
`X-CSRF-Token` header (HTMX `hx-headers`). A cross-site page cannot read our
cookie (browsers forbid that), so it can only ever send the cookie alone —
never a matching echoed value — which `verify_csrf` rejects.

CSRFCookieMiddleware ensures every request has a token, stashed on
`request.state.csrf_token` so templates can read `request.state.csrf_token`
directly (the `request` object is already in every Jinja context via
Starlette's TemplateResponse) without every single route having to thread
it through its own context dict by hand.
"""

import secrets

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.config import settings
from app.services.errors import CSRFError

CSRF_COOKIE_NAME = "csrf_token"


class CSRFCookieMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        existing = request.cookies.get(CSRF_COOKIE_NAME)
        token = existing or secrets.token_urlsafe(32)
        request.state.csrf_token = token

        response = await call_next(request)

        if existing is None:
            response.set_cookie(
                CSRF_COOKIE_NAME, token, httponly=True, samesite="lax", secure=settings.cookie_secure
            )
        return response


def verify_csrf(request: Request, submitted_token: str | None) -> None:
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not cookie_token or not submitted_token or not secrets.compare_digest(cookie_token, submitted_token):
        raise CSRFError()
