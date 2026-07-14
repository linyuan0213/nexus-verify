"""Image preprocessing filters based on OpenCV."""

from typing import Any

import cv2
import numpy as np
from PIL import Image

from nexus_verify.preprocessing.image import cv2_to_pil


def grayscale(image: np.ndarray) -> np.ndarray:
    """Convert BGR image to grayscale."""
    if len(image.shape) == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def binary(image: np.ndarray, threshold: int = 0) -> np.ndarray:
    """Binarize a grayscale image. Use Otsu if threshold is 0."""
    gray = grayscale(image)
    method = (
        cv2.THRESH_BINARY | cv2.THRESH_OTSU if threshold == 0 else cv2.THRESH_BINARY
    )
    _, binary_image = cv2.threshold(gray, threshold, 255, method)
    return binary_image


def denoise(image: np.ndarray, h: int = 30) -> np.ndarray:
    """Apply non-local means denoising."""
    gray = grayscale(image)
    return cv2.fastNlMeansDenoising(
        gray, h=h, templateWindowSize=11, searchWindowSize=21
    )


def border_white(image: np.ndarray, border: int = 5) -> np.ndarray:
    """Set the outer border pixels to white."""
    h, w = image.shape[:2]
    image[:border, :] = 255
    image[-border:, :] = 255
    image[:, :border] = 255
    image[:, -border:] = 255
    return image


def noise_unsome_pixel(image: np.ndarray) -> np.ndarray:
    """Remove isolated pixels whose neighbors are all different."""
    gray = grayscale(image)
    h, w = gray.shape
    out = gray.copy()
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            center = int(gray[y, x])
            neighbors = [
                int(gray[y - 1, x]),
                int(gray[y + 1, x]),
                int(gray[y, x - 1]),
                int(gray[y, x + 1]),
            ]
            matches = sum(1 for n in neighbors if n == center)
            if matches == 0:
                out[y, x] = 255
    return out


def edge_detect(image: np.ndarray, low: int = 50, high: int = 150) -> np.ndarray:
    """Apply Canny edge detection."""
    gray = grayscale(image)
    return cv2.Canny(gray, low, high)


def preprocess_captcha(
    image: np.ndarray, extra: dict[str, Any] | None = None
) -> Image.Image:
    """Default preprocessing pipeline for character captchas."""
    extra = extra or {}
    steps = extra.get(
        "preprocess_steps",
        ["grayscale", "binary", "denoise", "noise_unsome_pixel", "border_white"],
    )

    result = image
    for step in steps:
        if step == "grayscale":
            result = grayscale(result)
        elif step == "binary":
            result = binary(result)
        elif step == "denoise":
            result = denoise(result)
        elif step == "noise_unsome_pixel":
            result = noise_unsome_pixel(result)
        elif step == "border_white":
            result = border_white(result)
    return cv2_to_pil(result)
