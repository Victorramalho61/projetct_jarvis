import logging
import uuid
from contextvars import ContextVar

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

current_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
from services.app_logger import setup_log_forwarding
setup_log_forwarding("rh-service")

_logger = logging.getLogger(__name__)

from db import get_settings
from limiter import limiter
from routes.health import router as health_router
from routes.dashboard import router as dashboard_router
from routes.vagas import router as vagas_router
from routes.lookups import router as lookups_router
from routes.uploads import router as uploads_router
from routes.assinatura import router as assinatura_router
from routes.webhook_d4sign import router as webhook_d4sign_router


app = FastAPI(title="Jarvis RH Service")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_s = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _s.allowed_origins.split(",")],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-Trace-ID"],
    expose_headers=["X-Trace-ID"],
    max_age=600,
)


@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):
    tid = request.headers.get("X-Trace-ID") or uuid.uuid4().hex[:16]
    current_trace_id.set(tid)
    response = await call_next(request)
    response.headers["X-Trace-ID"] = tid
    return response


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception) -> JSONResponse:
    _logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(health_router)
app.include_router(dashboard_router)
app.include_router(vagas_router)
app.include_router(lookups_router)
app.include_router(uploads_router)
app.include_router(assinatura_router)
app.include_router(webhook_d4sign_router)
