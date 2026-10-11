"""Reject oversized HTTP bodies before they are parsed."""

from typing import Any

from starlette.responses import JSONResponse

from northstar.api.errors import error_payload


class LimitRequestSizeMiddleware:
    def __init__(self, app: Any, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        declared = _content_length(scope)
        if declared is None:
            await self.app(scope, receive, send)
            return
        if declared < 0:
            await _json(scope, receive, send, 400, "validation_error", "Content-Length is invalid.")
            return
        if declared > self.max_bytes:
            await _json(
                scope,
                receive,
                send,
                413,
                "payload_too_large",
                "Request body exceeds the size limit.",
            )
            return
        await self.app(scope, receive, send)


def _content_length(scope: dict[str, Any]) -> int | None:
    for key, value in scope.get("headers", []):
        if key.lower() == b"content-length":
            try:
                return int(value.decode("latin1"))
            except ValueError:
                return -1
    return None


async def _json(
    scope: dict[str, Any],
    receive: Any,
    send: Any,
    status_code: int,
    code: str,
    message: str,
) -> None:
    response = JSONResponse(status_code=status_code, content=error_payload(code, message))
    await response(scope, receive, send)
