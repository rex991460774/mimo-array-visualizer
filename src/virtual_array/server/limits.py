"""Request body size limits (the server has no auth, so every client is untrusted)."""

from __future__ import annotations

import json
from typing import Any

# JSON bodies are project documents of a few kB; 16 MB leaves ample room.
MAX_JSON_BODY_BYTES = 16 * 1024 * 1024
# Multipart framing around an uploaded file.
MULTIPART_OVERHEAD_BYTES = 1024 * 1024


class _BodyTooLargeError(Exception):
    pass


class BodySizeLimitMiddleware:
    """Reject request bodies above a per-path limit with 413.

    A declared Content-Length is checked before anything is read; chunked bodies
    are counted while the endpoint reads them, so neither form can stream an
    unbounded body into memory.
    """

    def __init__(self, app: Any, upload_limits: dict[str, int], default_limit: int = MAX_JSON_BODY_BYTES) -> None:
        self.app = app
        self.upload_limits = upload_limits
        self.default_limit = default_limit

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = self.upload_limits.get(scope["path"], self.default_limit)
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    declared = 0
                if declared > limit:
                    await _reject(send, limit)
                    return

        received = 0
        too_large = False
        rejected = False

        async def limited_receive() -> dict[str, Any]:
            nonlocal received, too_large
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    too_large = True
                    raise _BodyTooLargeError
            return message

        async def guarded_send(message: dict[str, Any]) -> None:
            # FastAPI turns errors raised while reading the body into its own 400
            # response; replace whatever comes back with the real reason.
            nonlocal rejected
            if not too_large:
                await send(message)
                return
            if not rejected:
                rejected = True
                await _reject(send, limit)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except _BodyTooLargeError:
            if not rejected:
                rejected = True
                await _reject(send, limit)


async def _reject(send: Any, limit: int) -> None:
    body = json.dumps({"detail": f"Request body exceeds {limit // (1024 * 1024)} MB."}).encode()
    await send({
        "type": "http.response.start",
        "status": 413,
        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
    })
    await send({"type": "http.response.body", "body": body})
