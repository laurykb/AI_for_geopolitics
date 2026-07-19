"""Limites globales des requêtes HTTP — protection avant validation et inférence."""

import asyncio

from fastapi.testclient import TestClient

from app.main import app
from app.request_limits import ExpensiveRequestLimitMiddleware


def test_oversized_request_body_is_rejected_before_route():
    client = TestClient(app)
    response = client.post(
        "/api/accounts",
        content=b'\x7b"name":"' + b"x" * 1_100_000 + b'"\x7d',
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413
    assert "volumineux" in response.json()["detail"]


def test_security_headers_and_private_no_store():
    client = TestClient(app)
    health = client.get("/health")
    assert health.headers["x-content-type-options"] == "nosniff"
    assert health.headers["x-frame-options"] == "DENY"
    private = client.get("/api/games/nope")
    assert private.headers["cache-control"] == "no-store"


def test_expensive_request_is_rejected_when_capacity_is_full():
    called = False

    async def downstream(scope, receive, send):
        nonlocal called
        called = True

    middleware = ExpensiveRequestLimitMiddleware(downstream, max_concurrent=1)
    assert middleware._slots.acquire(blocking=False)
    messages = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/games/g1/rounds",
        "headers": [],
    }
    try:
        asyncio.run(middleware(scope, receive, send))
    finally:
        middleware._slots.release()

    assert called is False
    start = next(message for message in messages if message["type"] == "http.response.start")
    assert start["status"] == 503
    assert (b"retry-after", b"2") in start["headers"]
