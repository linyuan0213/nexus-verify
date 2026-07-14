# Nexus Verify

多 Provider 验证码 / 图片验证服务。

## 特性

- `captcha`：普通字符验证码识别
- `click_captcha`：文字目标点选验证码（`target` 传入文字目标）
- `image_click_captcha`：图片目标点选验证码（`extra.target_b64` 传入目标图）
- `slide_captcha`：滑块验证码（`extra.slider_b64` 传入滑块图）
- `gap_match`：缺口匹配（`extra.slider_b64` 传入缺口图）
- `rotate_captcha`：旋转验证码（`extra.template_b64` 传入模板图）
- `text_ocr`：通用文字识别

默认使用 CPU 运行，无需 GPU，无需鉴权。

## 环境要求

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Docker + Docker Compose（可选，用于生产部署）

## 快速开始

本地开发：

```bash
uv sync
uv run python src/nexus_verify/main.py
```

或：

```bash
uv sync
uv run nexus-verify
```

服务默认监听 `http://0.0.0.0:9300`。

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/verify` | 提交验证任务 |
| GET | `/providers` | 列出已注册 Provider |
| GET | `/tasks` | 列出支持的任务类型 |
| GET | `/health` | 健康检查 |

### 通用请求格式

```bash
curl -X POST http://localhost:9300/verify \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "captcha",
    "provider": "ddddocr",
    "image_b64": "..."
  }'
```

`provider` 可选，留空时自动路由。

### 字符验证码

```bash
curl -X POST http://localhost:9300/verify \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "captcha",
    "image_b64": "..."
  }'
```

返回：`{"data": {"result": {"text": "AB12"}}}`

### 文字点选验证码

适用于“请点击文字：目标文字”类型的验证码。

```bash
curl -X POST http://localhost:9300/verify \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "click_captcha",
    "image_b64": "...",
    "target": "目标文字"
  }'
```

返回：`{"data": {"result": {"points": [[x1, y1], [x2, y2], ...]}}}`

### 图片点选验证码

适用于目标是一个小图条、需要在大图中找到对应图标的点选验证码。

```bash
curl -X POST http://localhost:9300/verify \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "image_click_captcha",
    "image_b64": "...",
    "extra": {"target_b64": "..."}
  }'
```

返回：`{"data": {"result": {"points": [[x1, y1], [x2, y2], ...]}}}`

### 滑块验证码

```bash
curl -X POST http://localhost:9300/verify \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "slide_captcha",
    "image_b64": "...",
    "extra": {"slider_b64": "..."}
  }'
```

返回：`{"data": {"result": {"distance": 123, "points": [[x, y]]}}}`

### 缺口匹配

```bash
curl -X POST http://localhost:9300/verify \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "gap_match",
    "image_b64": "...",
    "extra": {"slider_b64": "..."}
  }'
```

### 旋转验证码

```bash
curl -X POST http://localhost:9300/verify \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "rotate_captcha",
    "image_b64": "...",
    "extra": {"template_b64": "..."}
  }'
```

返回：`{"data": {"result": {"angle": 45, "confidence": 0.95}}}`

### 通用文字识别

```bash
curl -X POST http://localhost:9300/verify \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "text_ocr",
    "image_b64": "..."
  }'
```

返回：`{"data": {"result": {"text": "..."}}}`

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `NV_HOST` | `0.0.0.0` | 服务监听地址 |
| `NV_PORT` | `9300` | 服务监听端口 |
| `TZ` | - | 时区，建议 `Asia/Shanghai` |

## 部署

### 使用 Docker Compose（推荐）

```bash
just up
```

或手动：

```bash
docker compose up -d
```

Docker Compose 默认使用预构建镜像 `nexus-verify:latest`，无需本地构建。

### 镜像地址

- DockerHub：`linyuan0213/nexus-verify:latest`
- GitHub Container Registry：`ghcr.io/linyuan0213/nexus-verify:latest`

### 接入 nexus-media 完整模式

`nexus-media` 的 `docker-compose.yml` 已包含 `nexus-verify` 服务，完整模式启动时自动拉起：

```bash
cd /home/linyuan/python/nexus-media/backend
docker compose --profile full-mysql up -d
```

## 开发

```bash
uv run pytest tests/ -v
uv run pyright src/
```

## Just 命令

```bash
just list   # 查看所有命令
just up     # 部署 Docker Compose
just down   # 停止 Docker Compose
just logs   # 查看容器日志
just dev    # 本地运行开发服务
just test   # 运行测试
just lint   # 运行类型检查
just clean  # 清理缓存
```

## 许可证

MIT
