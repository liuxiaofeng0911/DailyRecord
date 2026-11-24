import logging
from contextlib import asynccontextmanager

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

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger("dailyrecord")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.auto_create:
        create_all()
        with SessionLocal() as db:
            ensure_seed_data(db)
    yield


app = FastAPI(title="每日照片记录 API", version="1.0.0", lifespan=lifespan)

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
    return JSONResponse(status_code=exc.http_status, content=fail(exc.code, exc.message))


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


from .routers import auth, entry, export, immich, photo, search, stats, system  # noqa: E402

app.include_router(auth.router)
app.include_router(entry.router)
app.include_router(photo.router)
app.include_router(stats.router)
app.include_router(immich.router)
app.include_router(export.router)
app.include_router(search.router)
app.include_router(system.router)


@app.get("/health")
def health():
    return ok({"status": "ok"})


@app.get("/ready")
def ready(db: Session = Depends(get_db)):
    db.execute(select(text("1")))
    return ok({"status": "ready", "database": "up"})
