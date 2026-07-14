"""HOG feature extraction for click-captcha visual matching."""

import cv2
import numpy as np
from PIL import Image


FEAT_SIZE = 32


def _to_hog(image: Image.Image | np.ndarray) -> np.ndarray:
    """Compute a simple HOG descriptor for a 32x32 normalized image."""
    if isinstance(image, Image.Image):
        gray = np.array(image.convert("L"))
    elif len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    gray = cv2.resize(gray, (FEAT_SIZE, FEAT_SIZE), interpolation=cv2.INTER_LANCZOS4)
    gray = gray.astype(np.float32) / 255.0

    dx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    dy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    magnitude = np.sqrt(dx * dx + dy * dy)
    orientation = np.arctan2(dy, dx) * 180.0 / np.pi
    orientation = np.where(orientation < 0, orientation + 180.0, orientation)

    cell_size = 8
    bins = 9
    cell_rows = FEAT_SIZE // cell_size
    cell_cols = FEAT_SIZE // cell_size
    cell_histograms = np.zeros((cell_rows, cell_cols, bins), dtype=np.float32)

    for row in range(cell_rows):
        for col in range(cell_cols):
            y1, y2 = row * cell_size, (row + 1) * cell_size
            x1, x2 = col * cell_size, (col + 1) * cell_size
            mag_cell = magnitude[y1:y2, x1:x2]
            ori_cell = orientation[y1:y2, x1:x2]
            for i in range(cell_size):
                for j in range(cell_size):
                    bin_idx = int(ori_cell[i, j] / 20.0) % bins
                    cell_histograms[row, col, bin_idx] += mag_cell[i, j]

    block_size = 2
    features: list[np.ndarray] = []
    for row in range(cell_rows - block_size + 1):
        for col in range(cell_cols - block_size + 1):
            block = cell_histograms[row : row + block_size, col : col + block_size].flatten()
            norm = np.linalg.norm(block) + 1e-7
            features.append(block / norm)

    return np.concatenate(features)


def extract_click_feature(image: Image.Image | np.ndarray) -> np.ndarray:
    """Extract a HOG feature vector from a grayscale or BGR image."""
    return _to_hog(image)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two feature vectors."""
    a = a - a.mean()
    b = b - b.mean()
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-7 or nb < 1e-7:
        return 0.0
    return float(np.dot(a, b) / (na * nb))
