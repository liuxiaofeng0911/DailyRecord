#!/usr/bin/env sh
# 从备份恢复：sh scripts/restore.sh backups/20261122-030000
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

SOURCE=${1:-}
if [ -z "$SOURCE" ] || [ ! -d "$SOURCE" ]; then
    echo "用法：sh scripts/restore.sh <备份目录>" >&2
    exit 1
fi

if [ -f .env ]; then
    # shellcheck disable=SC1091
    set -a; . ./.env; set +a
fi
COMPOSE="docker compose"
POSTGRES_USER=${POSTGRES_USER:-diary}
POSTGRES_DB=${POSTGRES_DB:-diary}

echo "!! 即将覆盖数据库 $POSTGRES_DB，按 Ctrl+C 取消，10 秒后继续"
sleep 10

echo "==> 重建数据库"
$COMPOSE exec -T postgres psql -U "$POSTGRES_USER" -d postgres -c \
    "DROP DATABASE IF EXISTS $POSTGRES_DB WITH (FORCE);"
$COMPOSE exec -T postgres psql -U "$POSTGRES_USER" -d postgres -c \
    "CREATE DATABASE $POSTGRES_DB OWNER $POSTGRES_USER;"

echo "==> 导入 dump"
cat "$SOURCE/diary.dump" | $COMPOSE exec -T postgres pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner

if [ -f "$SOURCE/uploads.tar.gz" ]; then
    echo "==> 恢复上传目录"
    mkdir -p backend/data
    tar -xzf "$SOURCE/uploads.tar.gz" -C backend/data
fi

echo "==> 重启服务"
$COMPOSE restart api

echo "恢复完成，请访问前端抽查数据。"
