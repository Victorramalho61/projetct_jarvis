import logging
import uuid
from contextlib import asynccontextmanager
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
setup_log_forwarding("performance-service")

_logger = logging.getLogger(__name__)

from db import get_settings
from limiter import limiter
from routes.health import router as health_router
from routes.evaluations import router as evaluations_router
from routes.admin import router as admin_router
from routes.notifications import router as notifications_router
from routes.management import router as management_router
from routes.indicators import router as indicators_router
from routes.public import router as public_router
from routes.my import router as my_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    _logger.info("Performance Service starting up")
    try:
        from services.sla_scheduler import start as _sla_start
        _sla_start()
    except Exception as exc:
        _logger.warning("SLA scheduler não iniciado: %s", exc)
    yield
    _logger.info("Performance Service shutting down")
    try:
        from services.sla_scheduler import stop as _sla_stop
        _sla_stop()
    except Exception:
        pass


app = FastAPI(title="Jarvis Performance Service", lifespan=lifespan)
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
app.include_router(evaluations_router)
app.include_router(admin_router)
app.include_router(notifications_router)
app.include_router(management_router)
app.include_router(indicators_router)
app.include_router(public_router)
app.include_router(my_router)
