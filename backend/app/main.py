import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .common import codes
from .common.exceptions import ApiError
from .common.result import fail, ok
from .config import settings
from .db import SessionLocal, create_all, get_db
from .services.bootstrap import ensure_seed_data
from .services.photo_service import run_purge_job
from .services.site_config import purge_hour_minute
from .services.timeutil import now_shanghai

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger("dailyrecord")


async def _purge_loop() -> None:
    """每分钟检查一次清理时间；所有者改配置后无需重启即可生效。"""
    while True:
        await asyncio.sleep(60)
        try:
            with SessionLocal() as db:
                hour, minute = purge_hour_minute(db)
                now = now_shanghai()
                target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if now < target:
                    continue
                result = await run_purge_job(db)
                if not result.get("skipped"):
                    logger.info("回收站清理完成: %s", result)
        except Exception:  # pragma: no cover - 后台任务防御
            logger.exception("回收站清理任务失败")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.auto_create:
        create_all()
        with SessionLocal() as db:
            ensure_seed_data(db)
    purge_task = None
    if settings.photo_purge_enabled and settings.env != "test":
        purge_task = asyncio.create_task(_purge_loop())
    yield
    if purge_task is not None:
        purge_task.cancel()
        with suppress(asyncio.CancelledError):
            await purge_task


app = FastAPI(title="每日记录 API", version=settings.app_version, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["token"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; connect-src 'self'; font-src 'self' data:;",
    )
    if settings.env == "prod":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    server_header = response.headers.get("server")
    if server_header:
        del response.headers["server"]
    return response


@app.exception_handler(ApiError)
async def api_error_handler(_request: Request, exc: ApiError):
    return JSONResponse(status_code=exc.http_status, content=fail(exc.code, exc.message, exc.data))


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError):
    errors = exc.errors()
    message = "参数错误"
    if errors:
        field = ".".join(str(p) for p in errors[0].get("loc", []) if p not in ("body", "query"))
        message = f"参数错误：{field} {errors[0].get('msg', '')}".strip()
    return JSONResponse(status_code=200, content=fail(codes.BAD_REQUEST, message))


@app.exception_handler(Exception)
async def unhandled_error_handler(_request: Request, exc: Exception):
    logger.exception("未处理异常: %s", exc)
    return JSONResponse(status_code=500, content=fail(codes.SERVER_ERROR, "服务器异常，请稍后再试"))


from .routers import (  # noqa: E402
    auth,
    entry,
    export,
    immich,
    org_share,
    photo,
    search,
    stats,
    system,
    tag,
)

app.include_router(auth.router)
app.include_router(entry.router)
app.include_router(photo.router)
app.include_router(tag.router)
app.include_router(stats.router)
app.include_router(immich.router)
app.include_router(export.router)
app.include_router(search.router)
app.include_router(system.router)
app.include_router(org_share.router)


@app.get("/health")
def health():
    return ok({"status": "ok", "version": settings.app_version})


@app.get("/ready")
def ready(db: Session = Depends(get_db)):
    db.execute(select(text("1")))
    return ok({"status": "ready", "database": "up"})
