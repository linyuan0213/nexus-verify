# Nexus Verify 设计文档

## 1. 项目定位

统一的验证码/图片验证服务，通过 HTTP API 接收各类验证任务，返回识别结果。

| 项目属性 | 值 |
|----------|-----|
| 项目名 | `nexus-verify` |
| Python 版本 | `>=3.12` |
| 包管理工具 | `uv` |
| GPU 支持 | 默认不开启 |
| 认证 | 不需要 |

## 2. 支持的验证方式

| 任务类型 | 说明 | 返回示例 |
|----------|------|----------|
| `captcha` | 字符验证码 | `{"text": "a7B9"}` |
| `click_captcha` | 图片点选验证码 | `{"points": [[x1, y1], [x2, y2]]}` |
| `slide_captcha` | 滑块验证码 | `{"distance": 120}` |
| `rotate_captcha` | 旋转验证码 | `{"angle": 45}` |
| `gap_match` | 缺口匹配 | `{"distance": 85}` |
| `text_ocr` | 通用文字识别 | `{"text": "..."}` |

## 3. 项目结构

```text
nexus-verify/
├── pyproject.toml
├── .python-version
├── Dockerfile
├── README.md
├── src/
│   └── nexus_verify/
│       ├── __init__.py
│       ├── main.py              # FastAPI 入口
│       ├── config.py            # Pydantic Settings
│       ├── api/
│       │   ├── router.py
│       │   └── schemas.py
│       ├── core/
│       │   ├── registry.py
│       │   ├── task.py
│       │   ├── result.py
│       │   └── exceptions.py
│       ├── preprocessing/       # 图像预处理工具
│       │   ├── __init__.py
│       │   ├── image.py         # 加载/解码
│       │   ├── filters.py       # 二值化/降噪/边缘检测
│       │   └── transforms.py    # 旋转/裁剪/缩放
│       ├── providers/
│       │   ├── base.py
│       │   ├── ddddocr.py       # 字符/点击/通用 OCR
│       │   ├── slide.py         # 滑块/缺口
│       │   ├── rotate.py        # 旋转
│       │   └── custom/          # 预留自定义训练模型
│       │       ├── __init__.py
│       │       └── provider.py
│       └── engine.py            # 任务调度
└── tests/
    ├── conftest.py
    ├── test_api.py
    ├── test_engine.py
    └── providers/
```

## 4. 核心抽象

```python
from abc import ABC, abstractmethod
from enum import StrEnum

class TaskType(StrEnum):
    CAPTCHA = "captcha"
    CLICK_CAPTCHA = "click_captcha"
    SLIDE_CAPTCHA = "slide_captcha"
    ROTATE_CAPTCHA = "rotate_captcha"
    GAP_MATCH = "gap_match"
    TEXT_OCR = "text_ocr"

class Provider(ABC):
    name: str
    tasks: set[TaskType]

    @property
    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    async def verify(self, task: VerifyTask) -> VerifyResult: ...
```

## 5. 图像预处理

所有 Provider 共享一个统一的预处理层，基于 OpenCV 实现。预处理由 `extra.preprocess` 控制，默认开启。

```text
src/nexus_verify/preprocessing/
├── image.py      # base64 / URL 解码、格式转换
├── filters.py    # 灰度、二值化、降噪、边缘检测、边框置白
└── transforms.py # 旋转、裁剪、缩放、透视变换
```

### 5.1 常用预处理方法

| 方法 | 作用 | 典型场景 |
|------|------|----------|
| `grayscale` | 转灰度图 | 所有验证码 |
| `binary` | 二值化（Otsu/固定阈值） | 字符验证码 |
| `denoise` | 非局部均值/中值滤波降噪 | 噪点验证码 |
| `border_white` | 四周置白 | 去除边框干扰线 |
| `noise_unsome_pixel` | 邻域非同色降噪 | 孤立噪点 |
| `edge_detect` | Canny 边缘检测 | 滑块/缺口匹配 |
| `resize` | 统一尺寸 | 模型输入规范化 |

### 5.2 预处理流程

```python
from nexus_verify.preprocessing.image import decode_image
from nexus_verify.preprocessing.filters import preprocess_captcha

async def verify(self, task: VerifyTask) -> VerifyResult:
    image = decode_image(task.image_b64)
    if task.extra.get("preprocess", True):
        image = preprocess_captcha(image)
    # 继续识别...
```

### 5.3 预处理配置

```json
{
  "task_type": "captcha",
  "image_b64": "...",
  "extra": {
    "preprocess": true,
    "preprocess_steps": ["grayscale", "binary", "denoise", "border_white"]
  }
}
```

## 6. API 设计

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/verify` | 通用验证入口 |
| GET | `/providers` | 列出可用 Provider |
| GET | `/tasks` | 列出支持的任务类型 |
| GET | `/health` | 健康检查 |

### 请求示例

```bash
POST /verify
{
  "task_type": "captcha",
  "image_b64": "iVBORw0KGgo...",
  "provider": "ddddocr",
  "extra": {"preprocess": true}
}
```

### 响应结构

```json
{
  "code": 0,
  "data": {
    "task_type": "captcha",
    "provider": "ddddocr",
    "result": {"text": "a7B9", "confidence": 0.95}
  },
  "message": "ok"
}
```

### 错误码

| code | 含义 |
|------|------|
| 0 | 成功 |
| -1 | 识别失败 / Provider 内部错误 |
| 400 | 请求参数错误 |
| 404 | 无可用 Provider |
| 422 | 校验失败 |
| 500 | 服务内部错误 |

## 7. Provider 选择策略

1. 请求中显式指定 `provider`
2. 配置项 `DEFAULT_PROVIDER_<TASK_TYPE>`
3. 注册表中第一个支持该 `task_type` 的 Provider

默认 Provider 为 `ddddocr`，负责 `captcha`、`click_captcha`、`text_ocr`。

## 8. pyproject.toml

```toml
[project]
name = "nexus-verify"
version = "2.0.0"
description = "Multi-provider verification service"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
    "loguru>=0.7",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "python-multipart>=0.0.9",
]

[project.optional-dependencies]
ddddocr = ["ddddocr>=1.3.1", "opencv-python-headless>=4.8", "Pillow>=10.0", "numpy"]
all = ["nexus-verify[ddddocr]"]

[project.scripts]
nexus-verify = "nexus_verify.main:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

## 9. 常用命令

```bash
# 同步依赖
uv sync

# 运行服务
uv run python src/nexus_verify/main.py

# 运行测试
uv run pytest tests/ -v

# 类型检查
uv run mypy src/
```

## 10. Dockerfile

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
COPY pyproject.toml .python-version src/ ./
RUN uv sync --extra all

EXPOSE 9300

CMD ["uv", "run", "python", "src/nexus_verify/main.py"]
```

## 11. 迁移计划

1. 初始化 uv 工程结构
2. 实现 Provider 抽象与 Registry
3. 实现通用预处理层（OpenCV 灰度/二值化/降噪/边框处理）
4. 实现 `ddddocr` Provider（字符验证码、点击、通用 OCR）
5. 实现 `slide`/`rotate`/`gap` Provider（基于 OpenCV）
6. 实现 API 与 Engine
7. 编写测试
8. 更新 Dockerfile 与 README
