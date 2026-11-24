"""Immich API 客户端：只封装日记需要的少量接口。"""

import asyncio
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
            detail = (response.text or "").strip().replace("\n", " ")[:300]
            raise ImmichError(
                f"Immich {method} {path} 返回 {response.status_code}"
                + (f": {detail}" if detail else "")
            )
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
        last_status = 0
        for attempt in range(3):
            async with self._client() as client:
                response = await client.get(
                    f"/api/assets/{asset_id}/thumbnail", params={"size": size}
                )
            if response.status_code < 400:
                return response.content, response.headers.get("content-type", "image/jpeg")
            last_status = response.status_code
            if response.status_code != 404 or attempt == 2:
                break
            # 刚上传的资产可能还在生成缩略图，短暂重试
            await asyncio.sleep(0.4)
        raise ImmichError(f"获取缩略图失败: {last_status}")

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

    async def create_admin_user(self, email: str, name: str, password: str) -> dict:
        return await self._request(
            "POST",
            "/api/admin/users",
            json={
                "email": email,
                "name": name,
                "password": password,
                "isAdmin": False,
                "shouldChangePassword": False,
            },
        )

    async def update_admin_user(self, user_id: str, password: str) -> dict:
        return await self._request(
            "PUT",
            f"/api/admin/users/{user_id}",
            json={"password": password, "shouldChangePassword": False},
        )

    async def list_admin_users(self) -> list[dict]:
        data = await self._request("GET", "/api/admin/users")
        return data if isinstance(data, list) else []

    async def login(self, email: str, password: str) -> dict:
        """用账号密码换取 Immich access token（仅开通阶段在内存中使用）。"""
        url = f"{self.base_url}/api/auth/login"
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
            response = await client.post(url, json={"email": email, "password": password})
        if response.status_code >= 400:
            raise ImmichError(f"Immich 登录失败: {response.status_code}")
        return response.json()

    async def create_api_key(
        self, access_token: str, name: str, permissions: list[str]
    ) -> str:
        url = f"{self.base_url}/api/api-keys"
        headers = {"Authorization": f"Bearer {access_token}", "accept": "application/json"}
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
            response = await client.post(
                url, headers=headers, json={"name": name, "permissions": permissions}
            )
        if response.status_code >= 400:
            raise ImmichError(f"Immich 创建 API Key 失败: {response.status_code}")
        secret = (response.json() or {}).get("secret")
        if not secret:
            raise ImmichError("Immich 未返回 API Key")
        return secret

    async def create_album(self, album_name: str) -> dict:
        return await self._request(
            "POST", "/api/albums", json={"albumName": album_name, "assetIds": []}
        )

    async def upload_asset(
        self, filename: str, content: bytes, mime_type: str, taken_at: datetime, album_id: str = ""
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
        target_album = album_id or settings.immich_album_id
        if target_album:
            try:
                await self._request(
                    "PUT",
                    f"/api/albums/{target_album}/assets",
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
