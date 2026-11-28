# 每日记录 DailyRecord

自托管的个人生活日记：每天一条记录，写下文字、心情、标签与照片，随时回看。

## 功能特性

- **每日记录**：文字、心情、标签、照片/视频；支持粘贴截图与移动端拍照
- **照片管理**：可选接入 Immich 照片库按日导入，回收站保留 30 天
- **回顾统计**：时间线筛选、年度热力图、连续记录天数、标签统计
- **组织共享**：成员双向确认后互相可见，组织可整体暂停
- **多用户与权限**：注册模式（关闭/开放/邀请码）、角色菜单、会话管理与在线撤销
- **AI 注释（可选）**：接入本地 Ollama 后，上传的照片与视频自动生成配文和关键词，可按日期范围批量补注释，并追加到当天记录
- **数据导出**：JSON / Markdown

## 技术栈与模块

| 模块 | 技术 | 职责 |
| --- | --- | --- |
| `frontend` | Vue 3 · Vuex · Vue Router · antdv-next · ECharts · Vite | 页面、组件、状态与接口调用 |
| `backend` | FastAPI · SQLAlchemy 2.0 · Alembic · PostgreSQL · Redis | 认证、记录、照片、共享、统计、导出 |
| `deploy` / `docker-compose.yml` | Nginx · Docker Compose | 网关反代、静态资源、服务编排 |
| `scripts` | Shell / Python | 构建、更新、备份恢复、版本号、密钥与 Immich 初始化 |

## 快速开始

1. 安装 Docker 与 Docker Compose
2. 准备配置：`cp .env.example .env`，至少填写 `POSTGRES_PASSWORD`、`IMMICH_DB_PASSWORD`、`JWT_SECRET`，并用 `python scripts/gen_keys.py` 生成 RSA 密钥
3. 一键构建启动：`sh scripts/build.sh`
4. 浏览器访问 `http://localhost:8080`

本地开发与调试（可与 docker 部署同时运行，端口不冲突）：

| 端 | 端口 | 说明 |
| --- | --- | --- |
| docker web | `8080` | 容器内 Nginx + 打包产物 |
| docker api | `8000` | 仅在容器网络内暴露，未映射到宿主，本机 `8000` 空闲 |
| 本地后端 | `8000` | `uvicorn --reload`，前端 `/api` 代理到这里 |
| 本地前端 | `5173` | Vite dev server；可用 `VITE_DEV_PORT` 覆盖 |

后端（IDEA 一键 Debug）：

1. 安装依赖：`cd backend && pip install -r requirements.txt`
2. 新建 Python 运行配置：module name 填 `uvicorn`，parameters 填 `app.main:app --reload --port 8000`，working directory 指向 `backend`
3. 直接 Debug 启动。后端会读取**仓库根目录的 `.env`**（`config.py` 里的 `ROOT_ENV`），因此本地调试与 docker 共用同一份配置、同一个数据库，改动即时可见
4. 若删掉了根 `.env`，则退回默认值：SQLite `backend/data/diary.db`（首次启动自动建表并写入种子数据），RSA 未配置会自动生成临时密钥

前端：

```bash
cd frontend
npm install
npm run dev    # http://localhost:5173
```

说明：`.env` 中的地址按**本地宿主视角**填写，docker 的 `postgres` / `redis` 固定映射到 `127.0.0.1:5432` / `127.0.0.1:6379`，Immich 为 `localhost:2283`，Ollama 为 `127.0.0.1:11434`；容器内由 `docker-compose.yml` 的 `environment` 覆盖成 `postgres:5432`、`redis:6379`、`immich-server:2283`、`host.docker.internal:11434`。所以本地 Debug 与 docker 版本读写的是同一套数据，无需额外改配置。

## 数据库与表结构

数据库脚本只保留**一份初始化建表脚本** `backend/alembic/versions/init_schema.py`，它按 `backend/app/models` 一次性创建全部表并写入种子数据，**不使用增量迁移**。

- 新库：容器启动时执行 `alembic upgrade head`，即跑这一份脚本。
- 改表结构：直接改模型文件，然后重建库；已有库不会被自动加列，需要保留旧数据时请自行迁移。
- 旧库残留的历史版本号会被 `alembic/env.py` 自动清理，再重新执行建表脚本（表已存在时为空操作）。

## 目录结构

```text
DailyRecord/
├── backend/     # FastAPI：app/{routers,services,models,schemas}、alembic 建表脚本（仅一份初始化）
├── frontend/    # Vue 3：src/{views,components,api,store,router}
├── deploy/      # Nginx 配置模板
├── scripts/     # 构建、更新、备份、密钥与 Immich 初始化
└── docker-compose.yml
```

## 常用脚本

| 命令 | 说明 |
| --- | --- |
| `sh scripts/build.sh` | 构建并启动（前端 8080 / 后端 8000） |
| `sh scripts/update.sh` | 拉取代码、重建并滚动更新 |
| `sh scripts/backup.sh` / `restore.sh` | 备份与恢复数据 |
| `sh scripts/version.sh` | 查看或设置版本号 |
| `python scripts/init_immich.py` | 初始化 Immich 管理员与 API Key |
