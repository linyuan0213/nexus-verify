# Nexus Verify development and deployment commands

# List all available recipes
list:
    @just --list

# Install dependencies
install:
    uv sync

# Start development server on port 9300
dev:
    uv run python src/nexus_verify/main.py

# Run tests
test:
    uv run pytest tests/ -v

# Run type checker
lint:
    uv run pyright src/

# Deploy via docker-compose (uses image nexus-verify:latest)
up:
    docker compose up -d

# Stop deployment
down:
    docker compose down

# View container logs
logs:
    docker compose logs -f

# Clean caches
clean:
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
    @echo "清理完成"
