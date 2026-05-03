import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")

from db import get_settings
from limiter import limiter
from routes.health import router as health_router
from routes.agents import router as agents_router
from routes.orchestrator import router as orchestrator_router
from routes.versioning import router as versioning_router
from services.scheduler import start_scheduler, stop_scheduler
from services.event_consumer import run_event_consumer

_consumer_task = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global _consumer_task
    start_scheduler()
    s = get_settings()
    _consumer_task = asyncio.create_task(
        run_event_consumer(poll_seconds=s.event_consumer_poll_seconds)
    )
    yield
    if _consumer_task:
        _consumer_task.cancel()
    stop_scheduler()


app = FastAPI(title="Jarvis Agents Service", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_s = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _s.allowed_origins.split(",")],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=600,
)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception) -> JSONResponse:
    logging.getLogger(__name__).exception("Unhandled error on %s %s",
                                          request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(health_router)
app.include_router(agents_router, prefix="/api")
app.include_router(orchestrator_router, prefix="/api")
app.include_router(versioning_router, prefix="/api")


@app.get("/metrics", include_in_schema=False)
async def prometheus_metrics():
    """Endpoint Prometheus — não exposto via Kong (apenas internal)."""
    from graph_engine.observability import generate_metrics_text
    return PlainTextResponse(generate_metrics_text(), media_type="text/plain; version=0.0.4")
