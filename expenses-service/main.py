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
from routes.expenses import router as expenses_router
from routes.governance import router as governance_router
from routes.payfly import router as payfly_router


async def _warm_payfly_cache() -> None:
    """Pré-aquece o cache PayFly para os anos mais comuns. Executa em background na startup."""
    from datetime import datetime
    from services.payfly import fetch_payfly_investments, fetch_payfly_investments_detail
    cur_year = datetime.now().year
    for year in [cur_year, cur_year - 1, None]:
        try:
            await asyncio.to_thread(fetch_payfly_investments, year)
            _logger.info("Cache PayFly investments pré-aquecido: year=%s", year)
        except Exception as exc:
            _logger.warning("Warm PayFly investments (year=%s): %s", year, exc)
        try:
            await asyncio.to_thread(fetch_payfly_investments_detail, year)
            _logger.info("Cache PayFly detail pré-aquecido: year=%s", year)
        except Exception as exc:
            _logger.warning("Warm PayFly detail (year=%s): %s", year, exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(_warm_payfly_cache())
    yield


app = FastAPI(title="Jarvis Expenses Service", lifespan=lifespan)
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
    logging.getLogger(__name__).exception("Unhandled error on %s %s",
                                          request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(health_router)
app.include_router(expenses_router, prefix="/api")
app.include_router(governance_router, prefix="/api")
app.include_router(payfly_router, prefix="/api")
