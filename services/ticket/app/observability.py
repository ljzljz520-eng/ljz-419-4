import logging
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware

TRACE_HEADER = "X-Trace-ID"
trace_id_var: ContextVar = ContextVar("trace_id", default="-")


def current_trace_id() -> str:
    return trace_id_var.get()


class TraceIdFilter(logging.Filter):
    def filter(self, record):
        record.trace_id = trace_id_var.get()
        return True


def setup_logging(service_name: str):
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s " + service_name +
        " trace_id=%(trace_id)s %(name)s: %(message)s"
    ))
    handler.addFilter(TraceIdFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


class TraceMiddleware(BaseHTTPMiddleware):
    """Bind the incoming (or freshly generated) trace ID to the request
    context, log one line per request, and echo the ID back to the caller."""

    async def dispatch(self, request, call_next):
        trace_id = request.headers.get(TRACE_HEADER) or uuid.uuid4().hex
        token = trace_id_var.set(trace_id)
        start = time.monotonic()
        try:
            response = await call_next(request)
        finally:
            trace_id_var.reset(token)
        elapsed_ms = (time.monotonic() - start) * 1000
        logging.getLogger("ticket.access").info(
            "%s %s -> %s %.1fms",
            request.method, request.url.path, response.status_code, elapsed_ms,
        )
        response.headers[TRACE_HEADER] = trace_id
        return response
