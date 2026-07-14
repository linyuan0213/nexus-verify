"""Provider registration helpers."""

from nexus_verify.providers.base import Provider
from nexus_verify.providers.custom import CustomProvider
from nexus_verify.providers.ddddocr import DdddOcrProvider
from nexus_verify.providers.image_click import ImageClickProvider
from nexus_verify.providers.rotate import RotateProvider
from nexus_verify.providers.slide import SlideProvider


def default_providers() -> list[Provider]:
    """Return the default set of provider instances."""
    return [
        DdddOcrProvider(),
        ImageClickProvider(),
        SlideProvider(),
        RotateProvider(),
        CustomProvider(),
    ]


__all__ = [
    "Provider",
    "DdddOcrProvider",
    "ImageClickProvider",
    "SlideProvider",
    "RotateProvider",
    "CustomProvider",
    "default_providers",
]
