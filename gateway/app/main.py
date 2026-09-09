import logging
import os

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles

from .observability import TRACE_HEADER, TraceMiddleware, current_trace_id, setup_logging

setup_logging("gateway")
logger = logging.getLogger("gateway")

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8001")
TICKET_SERVICE_URL = os.getenv("TICKET_SERVICE_URL", "http://localhost:8002")

HOP_BY_HOP = {"host", "content-length", "transfer-encoding", "content-encoding", "connection"}

app = FastAPI(title="gateway", version="1.0.0")
app.add_middleware(TraceMiddleware)

client = httpx.AsyncClient(timeout=10.0)


async def proxy(request: Request, base_url: str, target_path: str) -> Response:
    url = base_url + target_path
    if request.url.query:
        url += "?" + request.url.query
    headers = {
        k: v for k, v in request.headers.items() if k.lower() not in HOP_BY_HOP
    }
    headers[TRACE_HEADER] = current_trace_id()
    body = await request.body()
    try:
        upstream = await client.request(
            request.method, url, content=body, headers=headers
        )
    except httpx.HTTPError as exc:
        logger.error("upstream %s unreachable: %s", base_url, exc)
        return Response(status_code=502, content='{"detail":"upstream service unavailable"}',
                        media_type="application/json")
    logger.info("%s %s -> %s %s", request.method, request.url.path, base_url, upstream.status_code)
    resp_headers = {
        k: v for k, v in upstream.headers.items() if k.lower() not in HOP_BY_HOP
    }
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=resp_headers,
    )


@app.get("/health")
async def health():
    """Gateway is healthy itself; also reports downstream reachability."""
    downstream = {}
    for name, base in (("auth", AUTH_SERVICE_URL), ("ticket", TICKET_SERVICE_URL)):
        try:
            resp = await client.get(base + "/health", timeout=3.0)
            downstream[name] = "ok" if resp.status_code == 200 else "unhealthy"
        except httpx.HTTPError:
            downstream[name] = "unreachable"
    status = "ok" if all(v == "ok" for v in downstream.values()) else "degraded"
    return {"status": status, "service": "gateway", "downstream": downstream}


@app.api_route("/api/auth/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy_auth(path: str, request: Request):
    return await proxy(request, AUTH_SERVICE_URL, "/auth/" + path)


@app.api_route("/api/tickets", methods=["GET", "POST"])
async def proxy_tickets_root(request: Request):
    return await proxy(request, TICKET_SERVICE_URL, "/tickets")


@app.api_route("/api/tickets/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy_tickets(path: str, request: Request):
    return await proxy(request, TICKET_SERVICE_URL, "/tickets/" + path)


# Static frontend, mounted last so the API routes above win.
app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
