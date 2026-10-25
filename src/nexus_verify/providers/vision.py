"""OpenAI-compatible vision provider for image CAPTCHA recognition."""

import asyncio
import re
import time
from typing import Any

import httpx

from nexus_verify.config import settings
from nexus_verify.core.exceptions import RecognitionError
from nexus_verify.core.result import VerifyResult
from nexus_verify.core.task import TaskType, VerifyTask
from nexus_verify.providers.base import Provider


def clean_captcha_text(value: str, *, length: int | None = None) -> str:
    """Normalize a vision model answer to the lowercase alphanumeric CAPTCHA."""
    text = value or ""
    text = re.sub(r"```[a-zA-Z0-9_-]*", "", text)
    text = text.replace("```", "")
    text = text.strip().strip("\"'`").strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    candidate = lines[0] if lines else text
    tokens = re.findall(r"[A-Za-z0-9]+", candidate)
    if tokens:
        if length:
            preferred = [token for token in tokens if len(token) == int(length)]
            if preferred:
                candidate = preferred[0]
            elif all(len(token) == 1 for token in tokens):
                candidate = "".join(tokens)
            else:
                candidate = tokens[-1]
        elif all(len(token) == 1 for token in tokens):
            candidate = "".join(tokens)
        else:
            candidate = tokens[-1]
    candidate = re.sub(r"[^A-Za-z0-9]", "", candidate).lower()
    return candidate


class VisionProvider(Provider):
    """Recognize CAPTCHAs through an OpenAI-compatible vision endpoint."""

    name = "vision"
    tasks = {TaskType.CAPTCHA, TaskType.TEXT_OCR}

    def __init__(self) -> None:
        self._semaphore = asyncio.Semaphore(max(1, settings.vision_concurrency))

    @property
    def available(self) -> bool:
        return bool(settings.vision_api_url and settings.vision_api_key)

    async def verify(self, task: VerifyTask) -> VerifyResult:
        if not self.available:
            raise RecognitionError("vision provider is not configured")
        if not task.image_b64 and not task.image_url:
            raise RecognitionError("vision captcha requires image_b64 or image_url")

        extra = task.extra or {}
        model = str(extra.get("model") or settings.vision_model)
        prompt = str(extra.get("prompt") or settings.vision_prompt)
        max_tokens = int(extra.get("max_tokens") or settings.vision_max_tokens)
        image_url = task.image_url or f"data:image/png;base64,{task.image_b64}"

        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
            "temperature": float(extra.get("temperature", settings.vision_temperature)),
            "max_tokens": max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {settings.vision_api_key}",
            "Content-Type": "application/json",
        }
        endpoint = settings.vision_api_url.rstrip("/")
        if not endpoint.endswith("/chat/completions"):
            endpoint += "/chat/completions"
        retryable_status = {408, 409, 425, 429, 500, 502, 503, 504}
        max_retries = max(0, int(extra.get("max_retries", settings.vision_max_retries)))
        started = time.monotonic()

        body: dict[str, Any] | None = None
        attempts_used = 0
        async with self._semaphore:
            for attempt in range(max_retries + 1):
                attempts_used = attempt + 1
                try:
                    async with httpx.AsyncClient(timeout=settings.vision_timeout) as client:
                        response = await client.post(endpoint, json=payload, headers=headers)
                    response.raise_for_status()
                    body = response.json()
                    break
                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code
                    if status in retryable_status and attempt < max_retries:
                        await asyncio.sleep(settings.vision_retry_backoff * (2**attempt))
                        continue
                    raise RecognitionError(f"vision endpoint returned HTTP {status}") from exc
                except (httpx.HTTPError, ValueError) as exc:
                    if attempt < max_retries:
                        await asyncio.sleep(settings.vision_retry_backoff * (2**attempt))
                        continue
                    raise RecognitionError(f"vision request failed: {exc}") from exc

        if body is None:
            raise RecognitionError("vision request failed without a response")
        content = self._extract_content(body)
        text = clean_captcha_text(content, length=extra.get("length"))
        if not text:
            raise RecognitionError("vision model returned an empty captcha")
        return VerifyResult(
            text=text,
            confidence=None,
            raw={
                "model": model,
                "usage": body.get("usage"),
                "attempts": attempts_used,
                "latency_ms": round((time.monotonic() - started) * 1000),
            },
        )

    @staticmethod
    def _extract_content(body: dict[str, Any]) -> str:
        choices = body.get("choices") or []
        if not choices:
            return ""
        message = (choices[0] or {}).get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    parts.append(str(item.get("text") or ""))
            return "".join(parts)
        return str(content or "")


__all__ = ["VisionProvider", "clean_captcha_text"]
