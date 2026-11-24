#!/usr/bin/env sh
# 一键构建并启动：前端 8080，后端 8000
# 用法：
#   sh scripts/build.sh                 构建并启动
#   sh scripts/build.sh --pull          先拉取最新基础镜像
#   sh scripts/build.sh --no-cache      不使用构建缓存
#   sh scripts/build.sh --git-pull      先拉取代码再构建
#   sh scripts/build.sh --check         启动后等待健康检查
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

if docker compose version >/dev/null 2>&1; then
    COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE="docker-compose"
else
    echo "错误：未找到 Docker Compose（需要 docker compose 或 docker-compose）" >&2
    exit 1
fi

if [ ! -f .env ]; then
    cp .env.example .env
    echo "已生成 .env，请先填写数据库密码、JWT_SECRET、RSA 私钥/公钥后重试。" >&2
    exit 1
fi

GIT_PULL=0
PULL=0
NO_CACHE=0
CHECK=0

for arg in "$@"; do
    case "$arg" in
        --git-pull) GIT_PULL=1 ;;
        --pull) PULL=1 ;;
        --no-cache) NO_CACHE=1 ;;
        --check) CHECK=1 ;;
        -h|--help)
            sed -n '2,9p' "$0"
            exit 0
            ;;
        *)
            echo "未知参数：$arg" >&2
            exit 1
            ;;
    esac
done

if [ "$GIT_PULL" = "1" ]; then
    if [ -d .git ]; then
        echo "==> 拉取最新代码"
        git pull --ff-only
    else
        echo "!! 当前目录不是 Git 仓库，跳过 --git-pull"
    fi
fi

BUILD_FLAGS=""
if [ "$PULL" = "1" ]; then
    BUILD_FLAGS="$BUILD_FLAGS --pull"
fi
if [ "$NO_CACHE" = "1" ]; then
    BUILD_FLAGS="$BUILD_FLAGS --no-cache"
fi

echo "==> 构建镜像"
if [ -n "$BUILD_FLAGS" ]; then
    $COMPOSE build $BUILD_FLAGS
else
    $COMPOSE build
fi

echo "==> 启动服务"
$COMPOSE up -d --remove-orphans

echo "==> 当前状态"
$COMPOSE ps

WEB_PORT_VALUE=$(grep -E '^WEB_PORT=' .env 2>/dev/null | tail -n 1 | cut -d= -f2- | tr -d '"' || true)
WEB_PORT_VALUE=${WEB_PORT_VALUE:-8080}
echo ""
echo "前端入口：http://localhost:${WEB_PORT_VALUE}"
echo "后端接口：仅容器内网 api:8000（调试可临时映射）"

if [ "$CHECK" = "1" ]; then
    echo "==> 等待前端健康检查"
    attempt=0
    until [ "$attempt" -ge 30 ]; do
        if command -v curl >/dev/null 2>&1 && curl -fsS "http://127.0.0.1:${WEB_PORT_VALUE}/healthz" >/dev/null 2>&1; then
            echo "健康检查通过"
            exit 0
        fi
        if command -v wget >/dev/null 2>&1 && wget -qO- "http://127.0.0.1:${WEB_PORT_VALUE}/healthz" >/dev/null 2>&1; then
            echo "健康检查通过"
            exit 0
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    echo "健康检查未通过，最近日志：" >&2
    $COMPOSE logs --tail=80 api web >&2 || true
    exit 1
fi
