"""Garde-fou ASGI contre les corps de requête qui épuisent la mémoire du serveur."""

from __future__ import annotations

import threading

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class _BodyTooLarge(Exception):
    pass


class RequestBodyLimitMiddleware:
    """Refuse un body au-delà de ``max_bytes``, avec ou sans Content-Length."""

    def __init__(self, app: ASGIApp, max_bytes: int = 1_048_576) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        raw_length = headers.get(b"content-length")
        if raw_length is not None:
            try:
                if int(raw_length) > self.max_bytes:
                    await self._reject(scope, receive, send)
                    return
            except ValueError:
                # Une longueur invalide sera rejetée par le serveur HTTP ; le compteur
                # ci-dessous reste la seconde ligne de défense.
                pass

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _BodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _BodyTooLarge:
            await self._reject(scope, receive, send)

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send) -> None:
        response = JSONResponse({"detail": "corps de requête trop volumineux"}, status_code=413)
        await response(scope, receive, send)


class ExpensiveRequestLimitMiddleware:
    """Borne les streams/appels LLM simultanés pour préserver la latence du process."""

    _EXPENSIVE_SUFFIXES = ("/rounds", "/bot", "/flash", "/publish")

    def __init__(self, app: ASGIApp, max_concurrent: int = 8) -> None:
        self.app = app
        self._slots = threading.BoundedSemaphore(max(1, max_concurrent))

    @classmethod
    def _applies(cls, scope: Scope) -> bool:
        if scope.get("type") != "http" or scope.get("method") != "POST":
            return False
        path = str(scope.get("path") or "")
        return path.startswith("/api/games/") and path.endswith(cls._EXPENSIVE_SUFFIXES)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not self._applies(scope):
            await self.app(scope, receive, send)
            return
        if not self._slots.acquire(blocking=False):
            response = JSONResponse(
                {"detail": "serveur de simulation occupé — réessayez dans quelques secondes"},
                status_code=503,
                headers={"Retry-After": "2"},
            )
            await response(scope, receive, send)
            return
        try:
            await self.app(scope, receive, send)
        finally:
            self._slots.release()


class SecurityHeadersMiddleware:
    """Ajoute les protections navigateur utiles aux réponses de l'API."""

    _HEADERS = (
        (b"x-content-type-options", b"nosniff"),
        (b"x-frame-options", b"DENY"),
        (b"referrer-policy", b"no-referrer"),
        (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
    )
    _PRIVATE_PREFIXES = (
        "/api/games",
        "/api/players",
        "/api/accounts",
        "/api/markets",
        "/api/campaign/lab",
    )

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        path = str(scope.get("path") or "")

        async def secure_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {key.lower() for key, _ in headers}
                headers.extend(header for header in self._HEADERS if header[0] not in present)
                if path.startswith(self._PRIVATE_PREFIXES) and b"cache-control" not in present:
                    headers.append((b"cache-control", b"no-store"))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, secure_send)
