# Nexus Verify 开发与部署命令

# 显示所有可用命令（默认）
default:
    @just --list

# 安装依赖
install:
    uv sync

# 安装开发依赖
sync-dev:
    uv sync --dev

# 启动开发服务器，监听 9300 端口
dev:
    PYTHONPATH=src uv run python -m nexus_verify.main

# 运行测试，可传入额外 pytest 参数
test *args:
    uv run pytest tests/ -v {{args}}

# 运行 ruff 代码检查
lint:
    uv run ruff check .

# 运行类型检查
typecheck:
    uv run pyright src/ tests/

# 运行 lint + typecheck + test
check: lint typecheck test

# 本地构建 Docker 镜像
build:
    docker build -t nexus-verify:latest .

# 根据 pyproject.toml 版本号创建发布标签
tag-release:
    #!/usr/bin/env bash
    set -euo pipefail
    VERSION=$(uv run python -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")
    TAG="v${VERSION}"
    if git rev-parse "${TAG}" >/dev/null 2>&1; then
        echo "标签 ${TAG} 已存在。" >&2
        exit 1
    fi
    awk "/^## ${TAG} /{flag=1;next}/^## v/{flag=0}flag" README.md | grep -q . || echo "警告：README.md 中未找到 ${TAG} 的更新日志"
    git tag -a "${TAG}" -m "Release ${TAG}"
    echo "已创建标签 ${TAG}。推送触发发布：git push origin ${TAG}"

# 通过 docker-compose 部署
up:
    docker compose up -d

# 停止部署
down:
    docker compose down

# 查看容器日志
logs:
    docker compose logs -f

# 清理缓存
clean:
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name '*.pyc' -delete 2>/dev/null || true
    @echo "清理完成"
