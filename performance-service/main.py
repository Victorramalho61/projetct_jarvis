import asyncio
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

_logger = logging.getLogger(__name__)

from db import get_settings
from limiter import limiter
from routes.health import router as health_router
from routes.goals import router as goals_router
from routes.evaluations import router as evaluations_router
from routes.competencies import router as competencies_router
from routes.evidences import router as evidences_router
from routes.kpis import router as kpis_router
from routes.admin import router as admin_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    from services.benner_sync import start as _sync_start, stop as _sync_stop
    _sync_start()
    yield
    _sync_stop()


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
app.include_router(goals_router)
app.include_router(evaluations_router)
app.include_router(competencies_router)
app.include_router(evidences_router)
app.include_router(kpis_router)
app.include_router(admin_router)
