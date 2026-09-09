"""Trace-ID propagation and structured logging, shared by every service."""
import contextvars
import logging
import uuid

from starlette.middleware.base import BaseHTTPMiddleware

TRACE_HEADER = "X-Trace-ID"
trace_id_var = contextvars.ContextVar("trace_id", default="-")


class TraceIdFilter(logging.Filter):
    def filter(self, record):
        record.trace_id = trace_id_var.get()
        return True


def setup_logging(service_name):
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
    """Read X-Trace-ID from the request (or generate one) and bind it to the
    context so every log line emitted while handling the request carries it."""

    async def dispatch(self, request, call_next):
        trace_id = request.headers.get(TRACE_HEADER) or uuid.uuid4().hex
        token = trace_id_var.set(trace_id)
        try:
            response = await call_next(request)
            response.headers[TRACE_HEADER] = trace_id
            return response
        finally:
            trace_id_var.reset(token)


def current_trace_id():
    return trace_id_var.get()
