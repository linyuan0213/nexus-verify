"""Image loading and decoding utilities."""

import base64
import cv2
from io import BytesIO
from typing import Any

import numpy as np
from PIL import Image

from nexus_verify.core.exceptions import ImageDecodeError


ARRAY = np.ndarray[tuple[int, ...], np.dtype[np.integer | np.floating]]


def decode_base64(image_b64: str | None) -> Image.Image:
    """Decode a base64 string into a PIL Image."""
    if not image_b64:
        raise ImageDecodeError("image_b64 is empty")
    try:
        raw = base64.b64decode(image_b64.encode("utf-8"))
        return Image.open(BytesIO(raw)).convert("RGB")
    except Exception as exc:
        raise ImageDecodeError(f"Failed to decode base64 image: {exc}") from exc


def pil_to_cv2(image: Image.Image) -> "ARRAY":
    """Convert PIL RGB image to OpenCV BGR ndarray."""
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def cv2_to_pil(image: "ARRAY") -> Image.Image:
    """Convert OpenCV BGR ndarray to PIL RGB image."""

    return Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))


def load_image(task: Any) -> "ARRAY":
    """Load a task's image into OpenCV BGR format."""
    image = decode_base64(task.image_b64)
    return pil_to_cv2(image)
