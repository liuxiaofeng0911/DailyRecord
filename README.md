# 每日记录 DailyRecord

自托管的个人生活日记：每天一条记录，写下文字、心情、标签与照片，随时回看。

## 功能特性

- **每日记录**：文字、心情、标签、照片/视频；支持粘贴截图与移动端拍照
- **照片管理**：可选接入 Immich 照片库按日导入，回收站保留 30 天
- **回顾统计**：时间线筛选、年度热力图、连续记录天数、标签统计
- **组织共享**：成员双向确认后互相可见，组织可整体暂停
- **多用户与权限**：注册模式（关闭/开放/邀请码）、角色菜单、会话管理与在线撤销
- **数据导出**：JSON / Markdown；可选 AI 图片描述（Ollama）

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

本地开发：

| 端 | 命令 | 地址 |
| --- | --- | --- |
| 后端 | `cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000` | `http://localhost:8000` |
| 前端 | `cd frontend && npm install && npm run dev` | `http://localhost:5173` |

## 目录结构

```text
DailyRecord/
├── backend/     # FastAPI：app/{routers,services,models,schemas}、alembic 迁移
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
