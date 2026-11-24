#!/usr/bin/env python3
"""初始化 Immich 管理员与每日记录管理员 API Key（幂等）。

用法：
    python scripts/init_immich.py

读取仓库根目录 .env：
    IMMICH_PORT / IMMICH_ADMIN_EMAIL / IMMICH_ADMIN_PASSWORD / IMMICH_ADMIN_API_KEY
首次运行会创建 Immich 管理员并生成 API Key，写回 IMMICH_ADMIN_API_KEY。
"""

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"


def read_env() -> dict[str, str]:
    data: dict[str, str] = {}
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, value = line.split("=", 1)
            data[key.strip()] = value
    return data


def write_env(key: str, value: str) -> None:
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    replaced = False
    for index, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[index] = f"{key}={value}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def request(method: str, url: str, payload: dict | None = None, headers: dict | None = None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("accept", "application/json")
    if data is not None:
        req.add_header("content-type", "application/json")
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read().decode() or "{}"
            return response.status, json.loads(body)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode() or "{}"
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, {"raw": body}


def main() -> int:
    env = read_env()
    port = env.get("IMMICH_PORT") or "2283"
    base = f"http://127.0.0.1:{port}"
    email = env.get("IMMICH_ADMIN_EMAIL") or "admin@dailyrecord.local"
    password = env.get("IMMICH_ADMIN_PASSWORD") or ""
    existing_key = env.get("IMMICH_ADMIN_API_KEY") or ""
    if not password:
        print("错误：.env 中缺少 IMMICH_ADMIN_PASSWORD", file=sys.stderr)
        return 1

    if existing_key:
        status, _ = request("GET", f"{base}/api/admin/users", headers={"x-api-key": existing_key})
        if status == 200:
            print("管理员 API Key 已存在且可用，跳过。")
            return 0

    status, body = request(
        "POST",
        f"{base}/api/auth/admin-sign-up",
        {"email": email, "password": password, "name": "DailyRecord Admin"},
    )
    if status not in (200, 201) and "already" not in json.dumps(body).lower():
        print(f"创建 Immich 管理员失败：{status} {body}", file=sys.stderr)
        return 1
    print("Immich 管理员已就绪。")

    status, body = request(
        "POST", f"{base}/api/auth/login", {"email": email, "password": password}
    )
    if status not in (200, 201):
        print(f"登录 Immich 管理员失败：{status} {body}", file=sys.stderr)
        return 1
    token = body.get("accessToken")
    if not token:
        print("登录响应缺少 accessToken", file=sys.stderr)
        return 1

    status, body = request(
        "POST",
        f"{base}/api/api-keys",
        {"name": "dailyrecord-admin", "permissions": ["all"]},
        {"Authorization": f"Bearer {token}"},
    )
    if status not in (200, 201) or not body.get("secret"):
        print(f"创建管理员 API Key 失败：{status} {body}", file=sys.stderr)
        return 1
    secret = body["secret"]
    write_env("IMMICH_ADMIN_API_KEY", secret)
    print(f"已写入 IMMICH_ADMIN_API_KEY（尾号 {secret[-4:]}）。请重启 api 服务。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
