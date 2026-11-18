"""ASGI middleware for bounding incoming HTTP request bodies."""

from starlette.types import ASGIApp, Message, Receive, Scope, Send
from starlette.responses import JSONResponse


class RequestBodyLimitMiddleware:
    def __init__(self, app: ASGIApp, max_body_size: int) -> None:
        self.app = app
        self.max_body_size = max_body_size

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length:
            try:
                if int(content_length) > self.max_body_size:
                    await self._reject(scope, receive, send)
                    return
            except ValueError:
                pass

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue

            body.extend(message.get("body", b""))
            if len(body) > self.max_body_size:
                await self._reject(scope, receive, send)
                return
            if not message.get("more_body", False):
                break

        sent_body = False

        async def replay_body() -> Message:
            nonlocal sent_body
            if sent_body:
                return {"type": "http.request", "body": b"", "more_body": False}
            sent_body = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay_body, send)

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        response = JSONResponse(
            status_code=413,
            content={"detail": "Request body exceeds the allowed size."},
        )
        await response(scope, receive, send)
