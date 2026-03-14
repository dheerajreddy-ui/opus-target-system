"""Input sanitization middleware — keyword blocklist and regex filtering."""

import json
import re

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.bluestack.defense.defense_manager import DefenseManager

KEYWORD_BLOCKLIST = [
    "ignore previous",
    "ignore all",
    "disregard",
    "system prompt",
    "you are now",
    "pretend you are",
    "act as",
    "jailbreak",
    "dan mode",
    "ignore your instructions",
    "reveal your prompt",
    "show me your instructions",
]

INJECTION_PATTERNS = [
    # SQL injection
    re.compile(
        r"\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION)\b.*\b(FROM|INTO|SET|TABLE)\b",
        re.IGNORECASE,
    ),
    # Multiple SQL statements
    re.compile(r";\s*(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER)\b", re.IGNORECASE),
    # Base64 encoded payloads (long base64 strings)
    re.compile(r"[A-Za-z0-9+/]{50,}={0,2}"),
    # Hex encoded strings
    re.compile(r"(\\x[0-9a-fA-F]{2}){10,}"),
    # Markdown/XML injection attempts
    re.compile(r"<\s*(system|instruction|prompt)\b", re.IGNORECASE),
]


class InputSanitizerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method != "POST" or request.url.path != "/chat":
            return await call_next(request)

        dm = DefenseManager()
        if not dm.is_enabled("input_sanitizer"):
            return await call_next(request)

        body = await request.body()

        async def receive():
            return {"type": "http.request", "body": body}

        request = Request(request.scope, receive, request._send)

        try:
            data = json.loads(body)
            message = data.get("message", "")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return await call_next(request)

        message_lower = message.lower()

        # Keyword blocklist check
        if dm.is_enabled("keyword_blocklist"):
            for keyword in KEYWORD_BLOCKLIST:
                if keyword in message_lower:
                    return JSONResponse(
                        {"error": "Invalid input."},
                        status_code=400,
                    )

        # Regex filter check
        if dm.is_enabled("regex_filter"):
            for pattern in INJECTION_PATTERNS:
                if pattern.search(message):
                    return JSONResponse(
                        {"error": "Invalid input."},
                        status_code=400,
                    )

        return await call_next(request)
