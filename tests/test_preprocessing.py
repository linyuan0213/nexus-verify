"""Tests for image preprocessing utilities."""

import numpy as np
import pytest

from nexus_verify.preprocessing import (
    binary,
    border_white,
    decode_base64,
    grayscale,
)
from tests.conftest import make_image_b64


def test_decode_base64(sample_image_b64: str) -> None:
    image = decode_base64(sample_image_b64)
    assert image.size == (100, 40)


def test_grayscale() -> None:
    image = np.zeros((40, 100, 3), dtype=np.uint8)
    gray = grayscale(image)
    assert len(gray.shape) == 2


def test_binary() -> None:
    image = np.full((40, 100, 3), 128, dtype=np.uint8)
    binary_image = binary(image)
    assert len(binary_image.shape) == 2
    assert set(np.unique(binary_image)).issubset({0, 255})


def test_border_white() -> None:
    image = np.zeros((40, 100), dtype=np.uint8)
    image = border_white(image, border=3)
    assert image[0, 0] == 255
    assert image[0, 50] == 255
    assert image[39, 99] == 255
    assert image[20, 50] == 0
