"""Client for the auth service. Every call forwards the current trace ID so
the whole request chain is visible in the logs of both services."""
import logging
import os

import httpx
from fastapi import HTTPException

from .observability import TRACE_HEADER, current_trace_id

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8001")

logger = logging.getLogger("ticket.auth_client")


def _headers(authorization):
    return {
        "Authorization": authorization,
        TRACE_HEADER: current_trace_id(),
    }


async def verify_token(authorization: str) -> dict:
    """Validate the caller's JWT against the auth service. Returns
    {id, username, role}. Raises 401 when the token is rejected."""
    try:
        async with httpx.AsyncClient(base_url=AUTH_SERVICE_URL, timeout=5.0) as client:
            resp = await client.get("/auth/verify", headers=_headers(authorization))
    except httpx.HTTPError as exc:
        logger.error("auth service unreachable: %s", exc)
        raise HTTPException(status_code=503, detail="auth service unavailable")
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="invalid token")
    return resp.json()


async def fetch_user(user_id: int, authorization: str) -> dict:
    """Load a user from the auth service (used to validate an assignee)."""
    try:
        async with httpx.AsyncClient(base_url=AUTH_SERVICE_URL, timeout=5.0) as client:
            resp = await client.get(f"/auth/users/{user_id}", headers=_headers(authorization))
    except httpx.HTTPError as exc:
        logger.error("auth service unreachable: %s", exc)
        raise HTTPException(status_code=503, detail="auth service unavailable")
    if resp.status_code == 404:
        raise HTTPException(status_code=400, detail="assignee user not found")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="failed to fetch user from auth service")
    return resp.json()
