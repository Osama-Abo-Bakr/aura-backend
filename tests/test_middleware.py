"""
Integration tests for middleware — RequestID and AccessLog.
Uses FastAPI TestClient, no real DB/Redis connections.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.middleware import AccessLogMiddleware, RequestIDMiddleware


@pytest.fixture
def test_app():
    app = FastAPI()
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIDMiddleware)

    @app.get("/ping")
    async def ping():
        return {"pong": True}

    @app.get("/error")
    async def error():
        raise ValueError("boom")

    return app


@pytest.fixture
def client(test_app):
    return TestClient(test_app, raise_server_exceptions=False)


def test_request_id_generated_when_absent(client):
    resp = client.get("/ping")
    assert "X-Request-ID" in resp.headers
    request_id = resp.headers["X-Request-ID"]
    # Should be a valid UUID4 (36 chars with dashes)
    assert len(request_id) == 36
    assert request_id.count("-") == 4


def test_request_id_echoed_when_provided(client):
    custom_id = "my-custom-id-12345"
    resp = client.get("/ping", headers={"X-Request-ID": custom_id})
    assert resp.headers["X-Request-ID"] == custom_id


def test_request_id_unique_per_request(client):
    ids = {client.get("/ping").headers["X-Request-ID"] for _ in range(5)}
    assert len(ids) == 5  # all unique


def test_ping_returns_200(client):
    resp = client.get("/ping")
    assert resp.status_code == 200
    assert resp.json() == {"pong": True}
