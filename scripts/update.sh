#!/usr/bin/env sh
# 换包更新：拉代码 -> 拉基础镜像 -> 重新构建 -> 滚动重启 -> 清理悬空镜像
# 用法：
#   sh scripts/update.sh
#   sh scripts/update.sh --no-cache
#   sh scripts/update.sh --check
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

if [ -d .git ]; then
    echo "==> 拉取最新代码"
    git pull --ff-only
else
    echo "!! 当前目录不是 Git 仓库，跳过代码拉取"
fi

sh "$ROOT_DIR/scripts/build.sh" --pull "$@"

echo "==> 清理悬空镜像"
docker image prune -f --filter "dangling=true" >/dev/null 2>&1 || true

echo "更新完成。"
