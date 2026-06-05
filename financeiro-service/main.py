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
from app_logger import setup_log_forwarding
setup_log_forwarding("financeiro-service")

_logger = logging.getLogger(__name__)

from db import get_settings
from limiter import limiter
from routes.health import router as health_router
from routes.empresas import router as empresas_router
from routes.dashboard import router as dashboard_router
from routes.conciliacao import router as conciliacao_router
from routes.balanco import router as balanco_router
from routes.razao import router as razao_router
from routes.receitas import router as receitas_router
from routes.despesas import router as despesas_router
from routes.adiantamentos import router as adiantamentos_router
from routes.impostos_retidos import router as impostos_router
from routes.log_movimentacoes import router as log_mov_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    from services.dashboard_scheduler import start, stop
    start()
    yield
    stop()


app = FastAPI(title="Jarvis Financeiro Service", lifespan=lifespan)
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
app.include_router(empresas_router)
app.include_router(dashboard_router)
app.include_router(conciliacao_router)
app.include_router(balanco_router)
app.include_router(razao_router)
app.include_router(receitas_router)
app.include_router(despesas_router)
app.include_router(adiantamentos_router)
app.include_router(impostos_router)
app.include_router(log_mov_router)
