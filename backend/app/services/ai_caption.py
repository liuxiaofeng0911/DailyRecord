"""AI 注释：排队调用 Ollama 视觉模型，为照片与视频生成配文和关键词。"""

import asyncio
import io
import logging
import re
import tempfile
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from ..config import settings
from ..db import SessionLocal
from ..models import DailyEntry, Photo
from . import credential_service, storage
from .immich import ImmichError
from .ollama import OllamaError, analyze_image, merge_video_clip
from .timeutil import now_shanghai

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
# 送模型的边长上限：768 在 780M 核显上约 6 秒/张，再大收益很小、耗时翻倍
MAX_IMAGE_EDGE = 768
# 与前端记录正文长度限制保持一致
NOTE_LIMIT = 5000
DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")

_queue: asyncio.Queue[int] | None = None
_worker: asyncio.Task | None = None


def _downscale(content: bytes) -> bytes:
    """预览图缩到 768 长边再送模型，控制视觉 token 数与耗时。"""
    try:
        image = Image.open(io.BytesIO(content)).convert("RGB")
    except (UnidentifiedImageError, OSError):
        return content
    if max(image.size) <= MAX_IMAGE_EDGE:
        return content
    image.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE))
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=85)
    return buffer.getvalue()


def _ffmpeg_exe() -> str:
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
    except ImportError:  # pragma: no cover - 镜像内已安装
        return "ffmpeg"
    return get_ffmpeg_exe()


async def _run_ffmpeg(*args: str) -> tuple[int, bytes, bytes]:
    process = await asyncio.create_subprocess_exec(
        _ffmpeg_exe(),
        "-hide_banner",
        "-loglevel",
        "error",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    return process.returncode or 0, stdout, stderr


async def _duration_seconds(path: Path) -> float:
    process = await asyncio.create_subprocess_exec(
        _ffmpeg_exe(),
        "-hide_banner",
        "-i",
        str(path),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    match = DURATION_RE.search(stderr.decode("utf-8", "ignore"))
    if match is None:
        return 0.0
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


async def _frame_at(path: Path, at: float) -> bytes | None:
    code, stdout, _ = await _run_ffmpeg(
        "-ss",
        f"{at:.2f}",
        "-i",
        str(path),
        "-frames:v",
        "1",
        "-vf",
        f"scale='min({MAX_IMAGE_EDGE},iw)':-2",
        "-f",
        "image2pipe",
        "-vcodec",
        "mjpeg",
        "pipe:1",
    )
    return stdout if code == 0 and stdout else None


async def _video_source(db: Session, photo: Photo) -> tuple[Path, bool]:
    """返回视频本地路径与是否为临时文件（照片库视频需先下载）。"""
    if photo.storage_kind == "immich" and photo.immich_asset_id:
        content, _ = await storage.read_bytes(
            photo, size="original", client=credential_service.user_client(db, photo.user_id)
        )
        handle = tempfile.NamedTemporaryFile(prefix="dr-video-", suffix=".mp4", delete=False)
        handle.write(content)
        handle.close()
        return Path(handle.name), True
    if not photo.local_path:
        raise FileNotFoundError("视频文件不存在")
    path = Path(photo.local_path)
    if not path.exists():
        raise FileNotFoundError("视频文件不存在")
    return path, False


async def _video_frames(db: Session, photo: Photo) -> list[bytes]:
    """首帧、时间中点、尾帧各取一张，作为视频语义的三帧。"""
    path, temporary = await _video_source(db, photo)
    try:
        duration = await _duration_seconds(path)
        if duration > 1:
            points = [0.1, duration / 2, max(duration - 0.3, 0.1)]
        else:
            points = [0.1, 2.0, 4.0]
        frames: list[bytes] = []
        for point in points:
            frame = await _frame_at(path, point)
            if frame:
                frames.append(frame)
        return frames
    finally:
        if temporary:
            path.unlink(missing_ok=True)


def _note_line(photo: Photo, caption: str, keywords: list[str]) -> str:
    label = "视频" if photo.media_type == "VIDEO" else "照片"
    suffix = f"（关键词：{'、'.join(keywords)}）" if keywords else ""
    return f"【{label}】{caption}{suffix}"


def append_note_line(db: Session, photo: Photo, caption: str, keywords: list[str]) -> None:
    """把注释追加到当天记录正文末尾；同一行已存在则不重复追加。"""
    if not photo.entry_id or not caption:
        return
    entry = db.get(DailyEntry, photo.entry_id)
    if entry is None:
        return
    line = _note_line(photo, caption, keywords)
    note = (entry.note or "").rstrip()
    if line in note:
        return
    merged = f"{note}\n{line}" if note else line
    if len(merged) > NOTE_LIMIT:
        logger.info("记录正文已达 %s 字上限，跳过追加注释", NOTE_LIMIT)
        return
    entry.note = merged
    entry.version = int(entry.version or 0) + 1
    entry.update_user = photo.insert_user or entry.update_user
    entry.update_time = now_shanghai()


def _note_hint(db: Session, photo: Photo) -> str:
    if not photo.entry_id:
        return ""
    entry = db.get(DailyEntry, photo.entry_id)
    return entry.note if entry else ""


async def caption_photo(db: Session, photo: Photo) -> str:
    """生成并写入注释；失败抛 OllamaError/ImmichError/FileNotFoundError，由调用方处理。"""
    hint = _note_hint(db, photo)
    if photo.media_type == "VIDEO":
        frames = await _video_frames(db, photo)
        if not frames:
            raise OllamaError("视频抽帧失败，可能是编码不受支持")
        descriptions: list[str] = []
        for frame in frames:
            description, _ = await analyze_image(_downscale(frame), hint)
            if description:
                descriptions.append(description)
        if not descriptions:
            raise OllamaError("视频画面未能识别")
        caption, keywords = await merge_video_clip(descriptions, hint)
    else:
        content, _ = await storage.read_bytes(
            photo, size="preview", client=credential_service.user_client(db, photo.user_id)
        )
        caption, keywords = await analyze_image(_downscale(content), hint)

    if not caption:
        raise OllamaError("模型没有返回可用描述")
    photo.caption = caption[:1000]
    photo.ai_keywords = keywords
    photo.caption_source = "ai"
    photo.ai_state = "done"
    photo.ai_attempts = int(photo.ai_attempts or 0) + 1
    if settings.immich_write_description and photo.immich_asset_id and settings.immich_enabled:
        client = credential_service.user_client(db, photo.user_id)
        if client is not None:
            try:
                await client.update_description(photo.immich_asset_id, photo.caption)
            except ImmichError:
                pass
    append_note_line(db, photo, photo.caption, keywords)
    return photo.caption


async def _process(photo_id: int) -> None:
    with SessionLocal() as db:
        photo = db.get(Photo, photo_id)
        if photo is None or photo.deleted_at is not None:
            return
        if photo.media_type not in ("IMAGE", "VIDEO"):
            return
        if photo.caption_source == "manual":
            return
        if int(photo.ai_attempts or 0) >= MAX_ATTEMPTS:
            if photo.ai_state != "failed":
                photo.ai_state = "failed"
                db.commit()
            return
        try:
            await caption_photo(db, photo)
            db.commit()
            logger.info("照片 %s 自动注释完成：%s", photo_id, photo.caption[:40])
        except (OllamaError, ImmichError, FileNotFoundError) as exc:
            photo.ai_attempts = int(photo.ai_attempts or 0) + 1
            photo.ai_state = "failed"
            db.commit()
            logger.warning(
                "照片 %s 自动注释失败(%s/%s)：%s",
                photo_id,
                photo.ai_attempts,
                MAX_ATTEMPTS,
                exc,
            )


async def _consume(queue: asyncio.Queue[int]) -> None:
    """串行消费：本地 2B 视觉模型同时只跑一个，避免并发挤爆内存。"""
    while True:
        photo_id = await queue.get()
        try:
            await _process(photo_id)
        except Exception:  # pragma: no cover - 后台任务防御
            logger.exception("照片 %s 自动注释任务异常", photo_id)
        finally:
            queue.task_done()


def enqueue(photo_ids: list[int]) -> None:
    """把待注释素材加入后台队列；需在事件循环内调用（AI 未开启时直接跳过）。"""
    global _queue, _worker
    if not settings.ai_enabled or not photo_ids:
        return
    if _queue is None:
        _queue = asyncio.Queue()
    if _worker is None or _worker.done():
        _worker = asyncio.get_running_loop().create_task(_consume(_queue))
    for photo_id in photo_ids:
        _queue.put_nowait(int(photo_id))


def pending_count() -> int:
    return 0 if _queue is None else _queue.qsize()
