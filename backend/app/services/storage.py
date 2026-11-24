"""上传文件校验与存储。

优先存 Immich；未配置 Immich 时退化为本地目录（开发/单机模式）。
文件名一律 UUID 重命名，扩展名白名单，防止路径穿越。
"""

import io
import logging
import uuid
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

try:  # iPhone 的 HEIC/HEIF 需要额外解码器；缺失时仍支持其他格式
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:  # pragma: no cover - 依赖可选
    pass

from ..common import codes
from ..common.exceptions import ApiError
from ..config import settings
from ..models import Photo
from .immich import ImmichClient, ImmichError
from .timeutil import now_shanghai

logger = logging.getLogger(__name__)

# 浏览器可直接展示的格式：原样存储
IMAGE_FORMATS = {
    "JPEG": ("jpg", "image/jpeg"),
    "MPO": ("jpg", "image/jpeg"),  # 手机多帧 JPEG（微信/iPhone 常见）
    "PNG": ("png", "image/png"),
    "WEBP": ("webp", "image/webp"),
    "GIF": ("gif", "image/gif"),
    "BMP": ("bmp", "image/bmp"),
    "TIFF": ("tiff", "image/tiff"),
}
# 浏览器兼容性差或无法直接展示的格式（HEIF/HEIC/AVIF 等）统一转 JPEG
VIDEO_TYPES = {
    "video/mp4": "mp4",
    "video/quicktime": "mov",
    "video/webm": "webm",
    "video/x-matroska": "mkv",
    "video/x-msvideo": "avi",
    "video/x-m4v": "m4v",
    "video/mp4v-es": "m4v",
    "video/3gpp": "3gp",
    "video/mpeg": "mpeg",
    "video/mp2t": "ts",
    "video/hevc": "hevc",
}
VIDEO_EXTS = {
    "mp4": "video/mp4",
    "m4v": "video/x-m4v",
    "mov": "video/quicktime",
    "webm": "video/webm",
    "mkv": "video/x-matroska",
    "avi": "video/x-msvideo",
    "3gp": "video/3gpp",
    "mpg": "video/mpeg",
    "mpeg": "video/mpeg",
    "ts": "video/mp2t",
    "hevc": "video/hevc",
}
CHUNK = 1024 * 1024


def max_bytes() -> int:
    return settings.max_upload_mb * 1024 * 1024


async def read_upload(upload: UploadFile) -> bytes:
    buffer = io.BytesIO()
    total = 0
    while True:
        chunk = await upload.read(CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes():
            raise ApiError(codes.BAD_REQUEST, f"文件超过 {settings.max_upload_mb}MB 限制")
        buffer.write(chunk)
    return buffer.getvalue()


def _file_ext(filename: str) -> str:
    name = (filename or "").strip().lower()
    if "." not in name:
        return ""
    return name.rsplit(".", 1)[-1]


def _is_video(subtype: str, ext: str) -> bool:
    if subtype in VIDEO_TYPES:
        return True
    if subtype.startswith("video/"):
        return True
    # 手机/微信常见：content-type 缺失或为 application/octet-stream，只能靠扩展名
    return ext in VIDEO_EXTS and (not subtype or subtype == "application/octet-stream")


def _video_info(subtype: str, ext: str) -> dict:
    if subtype in VIDEO_TYPES:
        video_ext = VIDEO_TYPES[subtype]
    else:
        video_ext = ext if ext in VIDEO_EXTS else "mp4"
    mime = VIDEO_EXTS.get(video_ext) or (subtype if subtype.startswith("video/") else "video/mp4")
    return {
        "media_type": "VIDEO",
        "mime_type": mime,
        "ext": video_ext,
        "width": None,
        "height": None,
        "duration_ms": None,
    }


def _convert_to_jpeg(content: bytes) -> bytes:
    try:
        with Image.open(io.BytesIO(content)) as image:
            image.load()
            frame = image.convert("RGB") if image.mode not in ("RGB", "L") else image.copy()
            buffer = io.BytesIO()
            frame.save(buffer, format="JPEG", quality=92)
            return buffer.getvalue()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ApiError(codes.BAD_REQUEST, "图片解码失败，请换一张图片") from exc


def inspect_media(filename: str, content: bytes, content_type: str) -> dict:
    if not content:
        raise ApiError(codes.BAD_REQUEST, f"{filename} 内容为空")
    subtype = (content_type or "").split(";")[0].strip().lower()
    ext = _file_ext(filename)

    if _is_video(subtype, ext):
        return {**_video_info(subtype, ext), "content": content}

    try:
        with Image.open(io.BytesIO(content)) as image:
            image.verify()
        with Image.open(io.BytesIO(content)) as image:
            image_format = (image.format or "").upper()
            width, height = image.size
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ApiError(
            codes.BAD_REQUEST,
            f"{filename} 不是有效的图片文件（支持 JPG/PNG/WebP/GIF/BMP/TIFF/HEIC/AVIF）",
        ) from exc

    if image_format in IMAGE_FORMATS:
        out_ext, mime = IMAGE_FORMATS[image_format]
        final_content = content
    else:
        # 未知但可解码的格式（含 HEIC/AVIF）统一转 JPEG，保证浏览器与 Immich 都能显示
        final_content = _convert_to_jpeg(content)
        out_ext, mime = "jpg", "image/jpeg"
        logger.info("图片格式 %s 已转换为 JPEG：%s", image_format or "unknown", filename)

    return {
        "media_type": "IMAGE",
        "mime_type": mime,
        "ext": out_ext,
        "width": width,
        "height": height,
        "duration_ms": None,
        "content": final_content,
    }


def _local_dir(user_id: int) -> Path:
    path = settings.uploads_dir / str(user_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


async def store(
    *, user_id: int, filename: str, content: bytes, content_type: str
) -> dict:
    info = inspect_media(filename, content, content_type)
    payload = info.pop("content")
    taken_at = now_shanghai()
    if settings.immich_enabled:
        try:
            asset = await ImmichClient().upload_asset(
                f"{uuid.uuid4().hex}.{info['ext']}", payload, info["mime_type"], taken_at
            )
            return {
                **info,
                "storage_kind": "immich",
                "immich_asset_id": asset["id"],
                "local_path": None,
                "taken_at": asset.get("taken_at") or taken_at,
            }
        except ImmichError as exc:
            logger.warning("Immich 上传失败，退化为本地存储: %s", exc)

    target = _local_dir(user_id) / f"{uuid.uuid4().hex}.{info['ext']}"
    target.write_bytes(payload)
    return {
        **info,
        "storage_kind": "local",
        "immich_asset_id": None,
        "local_path": str(target),
        "taken_at": taken_at,
    }


async def read_bytes(photo: Photo, size: str = "preview") -> tuple[bytes, str]:
    if photo.storage_kind == "immich" and photo.immich_asset_id:
        client = ImmichClient()
        if size == "original":
            return await client.original(photo.immich_asset_id)
        return await client.thumbnail(photo.immich_asset_id, size="preview")
    if not photo.local_path:
        raise FileNotFoundError("照片文件不存在")
    path = Path(photo.local_path)
    if not path.exists():
        raise FileNotFoundError("照片文件不存在")
    return path.read_bytes(), photo.mime_type or "application/octet-stream"


def delete_local(photo: Photo) -> None:
    if photo.storage_kind != "local" or not photo.local_path:
        return
    try:
        Path(photo.local_path).unlink(missing_ok=True)
    except OSError as exc:  # pragma: no cover
        logger.warning("删除本地照片失败: %s", exc)
