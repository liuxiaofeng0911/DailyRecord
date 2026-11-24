#!/usr/bin/env sh
# 每日备份：PostgreSQL dump + 本地上传目录 + .env / compose 配置
# 用法：sh scripts/backup.sh [备份目录]
# 建议 crontab：0 3 * * * cd /opt/dailyrecord && sh scripts/backup.sh >> logs/backup.log 2>&1
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

BACKUP_ROOT=${1:-"$ROOT_DIR/backups"}
STAMP=$(date +%Y%m%d-%H%M%S)
TARGET="$BACKUP_ROOT/$STAMP"
mkdir -p "$TARGET"

if [ -f .env ]; then
    # shellcheck disable=SC1091
    set -a; . ./.env; set +a
fi
COMPOSE="docker compose"
POSTGRES_USER=${POSTGRES_USER:-diary}
POSTGRES_DB=${POSTGRES_DB:-diary}

echo "==> 导出 PostgreSQL"
$COMPOSE exec -T postgres pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB" > "$TARGET/diary.dump"

echo "==> 备份上传目录"
if [ -d backend/data/uploads ]; then
    tar -czf "$TARGET/uploads.tar.gz" -C backend/data uploads
elif docker volume inspect dailyrecord_pgdata >/dev/null 2>&1; then
    echo "!! 上传目录位于容器内，请按实际挂载路径调整本脚本" >&2
fi

echo "==> 备份配置"
cp .env "$TARGET/env.backup" 2>/dev/null || true
cp docker-compose.yml "$TARGET/" 2>/dev/null || true

echo "==> 生成校验和"
( cd "$TARGET" && sha256sum ./* > SHA256SUMS 2>/dev/null || true )

echo "备份完成：$TARGET"

# 保留最近 7 份
ls -1dt "$BACKUP_ROOT"/*/ 2>/dev/null | tail -n +8 | while read -r old; do
    rm -rf "$old"
done
