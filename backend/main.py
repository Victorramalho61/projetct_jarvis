import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

from db import get_settings, get_supabase
from routes.admin import router as admin_router
from routes.auth import router as auth_router
from routes.health import router as health_router
from routes.moneypenny import router as moneypenny_router
from routes.monitoring import router as monitoring_router
from routes.users import router as users_router
from services.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    get_supabase()
    logger.info("Supabase client ready")
    start_scheduler()
    yield
    stop_scheduler()
    logger.info("Shutdown")


app = FastAPI(title="Jarvis", lifespan=lifespan)

_settings = get_settings()
_origins = [o.strip() for o in _settings.allowed_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=600,
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(moneypenny_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(monitoring_router, prefix="/api")
