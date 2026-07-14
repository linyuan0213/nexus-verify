"""Geometric transforms for verification images."""

import cv2
import numpy as np


def resize(image: np.ndarray, width: int | None = None, height: int | None = None) -> np.ndarray:
    """Resize an image keeping aspect ratio if only one dimension is given."""
    h, w = image.shape[:2]
    if width is None and height is None:
        return image

    new_width: int
    new_height: int
    if width is None:
        new_height = height if height is not None else h
        new_width = int(w * new_height / h)
    elif height is None:
        new_width = width
        new_height = int(h * new_width / w)
    else:
        new_width = width
        new_height = height

    return cv2.resize(image, (new_width, new_height))


def crop(image: np.ndarray, x: int, y: int, w: int, h: int) -> np.ndarray:
    """Crop a region from the image."""
    return image[y : y + h, x : x + w]


def rotate(image: np.ndarray, angle: float, center: tuple[int, int] | None = None) -> np.ndarray:
    """Rotate image by the given angle in degrees."""
    h, w = image.shape[:2]
    if center is None:
        center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(image, matrix, (w, h))


def find_best_rotation(
    image: np.ndarray,
    template: np.ndarray,
    angles: range = range(-180, 181, 5),
) -> tuple[int, float]:
    """Find the rotation angle that best matches template by correlation."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    tmpl = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY) if len(template.shape) == 3 else template

    best_angle = 0
    best_score = -1.0
    for angle in angles:
        rotated = rotate(gray, angle)
        if rotated.shape != tmpl.shape:
            rotated = resize(rotated, width=tmpl.shape[1], height=tmpl.shape[0])
        result = cv2.matchTemplate(rotated, tmpl, cv2.TM_CCOEFF_NORMED)
        score = float(result.max())
        if score > best_score:
            best_score = score
            best_angle = angle
    return best_angle, best_score
