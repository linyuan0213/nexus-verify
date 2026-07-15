"""Tests for the image click provider."""

import base64
from io import BytesIO

import cv2
import numpy as np
import pytest
from PIL import Image

from nexus_verify.core.task import TaskType, VerifyTask
from nexus_verify.providers.image_click import ImageClickProvider


def _make_b64(image: Image.Image) -> str:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


@pytest.fixture
def provider() -> ImageClickProvider:
    return ImageClickProvider()


def _image_b64(width: int, height: int, color: tuple[int, int, int]) -> str:
    return _make_b64(Image.new("RGB", (width, height), color))


def test_extract_target_icons_by_projection(provider: ImageClickProvider) -> None:
    """Icons separated by gaps should be extracted as separate parts."""
    image = np.full((50, 170, 3), (100, 150, 200), dtype=np.uint8)
    # Draw three dark icons separated by gaps.
    image[:, 10:40, :] = (0, 0, 0)
    image[:, 70:100, :] = (0, 0, 0)
    image[:, 130:160, :] = (0, 0, 0)

    icons = provider._extract_target_icons(image)
    assert len(icons) == 3
    assert icons[0].shape[1] == 30
    assert icons[1].shape[1] == 30
    assert icons[2].shape[1] == 30


def test_extract_target_icons_fallback(provider: ImageClickProvider) -> None:
    """When no gaps are found, the image is split into equal columns."""
    image = np.full((50, 150, 3), (0, 0, 0), dtype=np.uint8)

    icons = provider._extract_target_icons(image)
    assert len(icons) == 3
    assert icons[0].shape[1] == 50
    assert icons[1].shape[1] == 50
    assert icons[2].shape[1] == 50


def test_detect_candidates_finds_icons(provider: ImageClickProvider) -> None:
    """Dark icons on a light background should be detected as candidates."""
    background = np.full((200, 300, 3), (255, 255, 255), dtype=np.uint8)
    cv2.rectangle(background, (30, 40), (70, 80), (0, 0, 0), -1)
    cv2.rectangle(background, (150, 120), (190, 160), (0, 0, 0), -1)

    candidates = provider._detect_candidates(background)
    assert len(candidates) == 2
    centers = {(x + w // 2, y + h // 2) for x, y, w, h in candidates}
    assert (50, 60) in centers
    assert (170, 140) in centers


def test_match_icons_returns_centers(provider: ImageClickProvider) -> None:
    """A target icon should match its corresponding candidate in the background."""
    # Build a simple background with two black squares.
    background = np.full((200, 300, 3), (255, 255, 255), dtype=np.uint8)
    cv2.rectangle(background, (30, 40), (70, 80), (0, 0, 0), -1)
    cv2.rectangle(background, (150, 120), (190, 160), (0, 0, 0), -1)

    target = np.full((50, 50, 3), (255, 255, 255), dtype=np.uint8)
    cv2.rectangle(target, (10, 10), (40, 40), (0, 0, 0), -1)

    candidates = provider._detect_candidates(background)
    points = provider._match_icons([target], candidates, background)
    assert len(points) == 1
    x, y = points[0]
    # Both squares are identical; the returned point should be one of the two centers.
    assert (x, y) in {(50, 60), (170, 140)}


@pytest.mark.asyncio
async def test_verify_requires_target_b64(provider: ImageClickProvider) -> None:
    """Missing target_b64 should raise an error."""
    task = VerifyTask(
        task_type=TaskType.IMAGE_CLICK_CAPTCHA,
        image_b64=_image_b64(100, 100, (255, 255, 255)),
    )
    with pytest.raises(Exception):  # ImageDecodeError
        await provider.verify(task)


@pytest.mark.asyncio
async def test_verify_no_candidates(provider: ImageClickProvider) -> None:
    """A blank background should result in no candidates."""
    task = VerifyTask(
        task_type=TaskType.IMAGE_CLICK_CAPTCHA,
        image_b64=_image_b64(100, 100, (255, 255, 255)),
        extra={"target_b64": _image_b64(30, 30, (0, 0, 0))},
    )
    with pytest.raises(Exception):  # RecognitionError
        await provider.verify(task)
