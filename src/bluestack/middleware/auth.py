"""Bearer token authentication middleware."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.bluestack.defense.defense_manager import DefenseManager

# Hardcoded test tokens for development
VALID_TOKENS = {
    "test-token-acme-001": {"user_id": "user_1", "role": "customer"},
    "test-token-acme-002": {"user_id": "user_2", "role": "customer"},
    "test-token-admin-001": {"user_id": "admin_1", "role": "admin"},
}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip auth for non-protected endpoints
        if request.url.path in ("/health", "/docs", "/openapi.json"):
            return await call_next(request)

        dm = DefenseManager()
        if not dm.is_enabled("auth_required"):
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                {"error": "Authentication required. Provide Bearer token."},
                status_code=401,
            )

        token = auth_header[7:]
        if token not in VALID_TOKENS:
            return JSONResponse(
                {"error": "Invalid authentication token."},
                status_code=401,
            )

        # Attach user info to request state
        request.state.user = VALID_TOKENS[token]
        return await call_next(request)
