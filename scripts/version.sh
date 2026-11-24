#!/usr/bin/env sh
# 版本号工具（可被其它脚本 source）
# 用法：
#   sh scripts/version.sh            输出当前版本
#   sh scripts/version.sh --next     输出下一个补丁版本 X.X.(X+1)
#   sh scripts/version.sh 1.2.3      校验并输出规范版本（可带 v 前缀）
#   sh scripts/version.sh --set 1.2.3  写入 VERSION 文件
set -eu

VERSION_REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
VERSION_FILE="$VERSION_REPO_ROOT/VERSION"

is_semver() {
    printf '%s' "$1" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'
}

current_version() {
    version=""
    if [ -f "$VERSION_FILE" ]; then
        version=$(tr -d ' \r\n' < "$VERSION_FILE")
    fi
    if ! is_semver "$version"; then
        # 兜底：从 package.json 读取，保证老仓库也能启动
        version=$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' \
            "$VERSION_REPO_ROOT/frontend/package.json" 2>/dev/null | head -n 1)
    fi
    if ! is_semver "$version"; then
        version="0.0.0"
    fi
    printf '%s\n' "$version"
}

next_version() {
    base="$1"
    major=$(printf '%s' "$base" | cut -d. -f1)
    minor=$(printf '%s' "$base" | cut -d. -f2)
    patch=$(printf '%s' "$base" | cut -d. -f3)
    printf '%s.%s.%s\n' "$major" "$minor" "$((patch + 1))"
}

normalize_version() {
    value=$1
    value=${value#v}
    value=${value#V}
    if ! is_semver "$value"; then
        return 1
    fi
    printf '%s\n' "$value"
}

write_version() {
    printf '%s\n' "$1" > "$VERSION_FILE"
}

if [ "${0##*/}" = "version.sh" ]; then
    case "${1:-}" in
        ""|--current)
            current_version
            ;;
        --next)
            next_version "$(current_version)"
            ;;
        --set)
            if [ $# -lt 2 ]; then
                echo "用法：sh scripts/version.sh --set <X.Y.Z>" >&2
                exit 1
            fi
            if ! value=$(normalize_version "$2"); then
                echo "版本号格式不正确：$2（应为 X.Y.Z）" >&2
                exit 1
            fi
            write_version "$value"
            echo "已写入版本：$value"
            ;;
        -h|--help)
            sed -n '2,9p' "$0"
            ;;
        -*)
            echo "未知参数：$1" >&2
            exit 1
            ;;
        *)
            if ! normalize_version "$1"; then
                echo "版本号格式不正确：$1（应为 X.Y.Z）" >&2
                exit 1
            fi
            ;;
    esac
fi
