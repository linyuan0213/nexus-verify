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
PYTHONPATH=src uv run python -m nexus_verify.main
```

服务默认监听 `http://0.0.0.0:9300`。

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/verify` | 提交验证任务 |
| GET | `/providers` | 列出已注册 Provider |
| GET | `/tasks` | 列出支持的任务类型 |
| POST | `/face/bbox` | 检测图片中的人脸矩形框 |
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

## 分支与版本发布

项目采用 `dev -> release -> master` 分支流：

- `dev`：日常开发分支，推送后自动构建 `latest-beta` 镜像。
- `release`：稳定化分支，合并前需通过 CI。
- `master`：生产分支，通过 `v*` 标签触发正式发布。

### 发布步骤

1. 在 `pyproject.toml` 和 `src/nexus_verify/__init__.py` 中更新版本号。
2. 在 README 的 `## 更新日志` 下补充该版本说明。
3. 创建标签并推送：

```bash
just tag-release
# 或手动：
git tag -a v2.0.0 -m "Release v2.0.0"
git push origin v2.0.0
```

推送 `v*` 标签后，GitHub Actions 会自动：

- 运行 CI（lint / typecheck / test）
- 构建并推送 linux/amd64 + linux/arm64 镜像到 DockerHub 和 GHCR
- 创建 GitHub Release（正文从 README 更新日志提取）
- 发送 Telegram 通知

## 开发

```bash
uv run pytest tests/ -v
uv run pyright src/
```

## Just 命令

```bash
just list         # 查看所有命令
just up           # 部署 Docker Compose
just down         # 停止 Docker Compose
just logs         # 查看容器日志
just dev          # 本地运行开发服务
just test         # 运行测试
just lint         # 运行 ruff 代码检查
just typecheck    # 运行类型检查
just check        # 运行 lint + typecheck + test
just build        # 本地构建 Docker 镜像
just tag-release  # 根据 pyproject.toml 版本创建发布标签
just clean        # 清理缓存
```

## 更新日志

### v2.1.0

- 新增 `POST /face/bbox` 人脸检测接口，返回图片尺寸与人脸矩形框，供裁剪/构图场景使用。
- `captcha` 新增 `raw`、`line_remove`、`ensemble` 识别选项，支持原图识别、去横线识别和多预处理逐位投票。
- `text_ocr` 检测不到文本框时回退整图分类，提升动画/影视硬字幕识别。

### v2.0.3

- `text_ocr` 在检测不到文本框时回退到整图分类，提升动画/影视硬字幕识别。
- 字幕检测场景下可识别大字号、描边及彩色字幕。

### v2.0.0

- 初始稳定版本：支持 captcha / click_captcha / image_click_captcha / slide_captcha / gap_match / rotate_captcha / text_ocr 等多种验证任务。
- 基于 FastAPI 提供 RESTful API。
- 提供 Docker / Docker Compose 部署方式。

## 许可证

MIT

## 视觉模型 Provider

除了本地 OCR，nexus-verify 支持 OpenAI 兼容的视觉模型识别验证码。

配置环境变量：

```bash
NV_VISION_API_URL=https://api.example.com/v1/chat/completions
NV_VISION_API_KEY=your-key
NV_VISION_MODEL=qwen-vl-ocr
NV_VISION_PROMPT="Read the CAPTCHA. Return only the characters, lowercase."
NV_VISION_MAX_TOKENS=1000
NV_VISION_TIMEOUT=60
```

调用时指定 provider：

```json
{
  "task_type": "captcha",
  "provider": "vision",
  "image_b64": "...",
  "extra": {"length": 5}
}
```

行为：

- `vision_api_url` 或 `vision_api_key` 未配置时，provider 显示为不可用
- 返回内容会剥离代码块、引号、空白，只保留小写字母和数字
- HTTP/解析失败统一返回可识别的错误，不泄露密钥
- 插件侧采用 `vision` 优先、`ddddocr` 回退

可用性检查：

```bash
curl http://127.0.0.1:9300/providers
```
