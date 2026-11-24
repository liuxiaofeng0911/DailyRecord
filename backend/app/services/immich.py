"""Immich API 客户端：只封装日记需要的少量接口。"""

from datetime import datetime
from typing import Any

import httpx

from ..config import settings
from ..services.timeutil import to_shanghai


class ImmichError(RuntimeError):
    pass


class ImmichClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None) -> None:
        self.base_url = (base_url or settings.immich_url).rstrip("/")
        self.api_key = api_key or settings.immich_api_key

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            headers={"x-api-key": self.api_key, "accept": "application/json"},
            timeout=httpx.Timeout(60.0, connect=5.0),
        )

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        if not self.configured:
            raise ImmichError("Immich 未配置")
        try:
            async with self._client() as client:
                response = await client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise ImmichError(f"Immich 连接失败: {exc}") from exc
        if response.status_code >= 400:
            raise ImmichError(f"Immich {method} {path} 返回 {response.status_code}")
        content_type = response.headers.get("content-type", "")
        if content_type.startswith("application/json"):
            return response.json()
        return response.content

    async def about(self) -> dict:
        return await self._request("GET", "/api/server/about")

    async def search_assets(
        self, taken_after: datetime, taken_before: datetime, size: int = 200
    ) -> list[dict]:
        payload = {
            "takenAfter": taken_after.isoformat() + "Z",
            "takenBefore": taken_before.isoformat() + "Z",
            "size": min(size, 1000),
            "page": 1,
            "withExif": True,
        }
        data = await self._request("POST", "/api/search/metadata", json=payload)
        items = (data.get("assets") or {}).get("items") or []
        return [self._normalize(item) for item in items]

    async def get_asset(self, asset_id: str) -> dict:
        return self._normalize(await self._request("GET", f"/api/assets/{asset_id}"))

    async def thumbnail(self, asset_id: str, size: str = "preview") -> tuple[bytes, str]:
        async with self._client() as client:
            response = await client.get(
                f"/api/assets/{asset_id}/thumbnail", params={"size": size}
            )
        if response.status_code >= 400:
            raise ImmichError(f"获取缩略图失败: {response.status_code}")
        return response.content, response.headers.get("content-type", "image/jpeg")

    async def original(self, asset_id: str) -> tuple[bytes, str]:
        async with self._client() as client:
            response = await client.get(f"/api/assets/{asset_id}/original")
        if response.status_code >= 400:
            raise ImmichError(f"获取原图失败: {response.status_code}")
        return response.content, response.headers.get(
            "content-type", "application/octet-stream"
        )

    async def update_description(self, asset_id: str, description: str) -> None:
        await self._request(
            "PUT", "/api/assets", json={"ids": [asset_id], "description": description}
        )

    async def delete_asset(self, asset_id: str) -> None:
        await self._request("DELETE", "/api/assets", json={"ids": [asset_id]})

    async def upload_asset(
        self, filename: str, content: bytes, mime_type: str, taken_at: datetime
    ) -> dict:
        if not self.configured:
            raise ImmichError("Immich 未配置")
        stamp = taken_at.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        data = {
            "deviceAssetId": f"dailyrecord-{filename}-{stamp}",
            "deviceId": "dailyrecord",
            "fileCreatedAt": stamp,
            "fileModifiedAt": stamp,
            "isFavorite": "false",
        }
        files = {"assetData": (filename, content, mime_type or "application/octet-stream")}
        asset = await self._request("POST", "/api/assets", data=data, files=files)
        if settings.immich_album_id:
            try:
                await self._request(
                    "PUT",
                    f"/api/albums/{settings.immich_album_id}/assets",
                    json={"ids": [asset["id"]]},
                )
            except ImmichError:
                pass
        normalized = self._normalize(asset)
        if not normalized.get("taken_at"):
            normalized["taken_at"] = taken_at
        return normalized

    @staticmethod
    def _normalize(item: dict) -> dict:
        exif = item.get("exifInfo") or {}
        raw_taken = (
            item.get("localDateTime")
            or exif.get("dateTimeOriginal")
            or item.get("fileCreatedAt")
        )
        taken_at = None
        if raw_taken:
            try:
                parsed = datetime.fromisoformat(str(raw_taken).replace("Z", "+00:00"))
                taken_at = to_shanghai(parsed)
            except ValueError:
                taken_at = None
        return {
            "id": item.get("id") or "",
            "type": item.get("type", "IMAGE"),
            "mime_type": item.get("originalMimeType") or exif.get("mimeType") or "",
            "taken_at": taken_at,
            "description": item.get("description") or "",
            "original_file_name": item.get("originalFileName") or "",
        }
