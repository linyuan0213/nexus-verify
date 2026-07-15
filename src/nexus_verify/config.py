"""Application configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_prefix="NV_")

    app_name: str = "Nexus Verify"
    host: str = "0.0.0.0"
    port: int = 9300
    reload: bool = False

    default_provider_captcha: str = "ddddocr"
    default_provider_click_captcha: str = "ddddocr"
    default_provider_image_click_captcha: str = "image_click"
    default_provider_text_ocr: str = "ddddocr"
    default_provider_slide_captcha: str = "slide"
    default_provider_rotate_captcha: str = "rotate"
    default_provider_gap_match: str = "slide"


settings = Settings()
