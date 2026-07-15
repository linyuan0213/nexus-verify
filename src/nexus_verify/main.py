"""Application entry point."""

import uvicorn
from fastapi import FastAPI

from nexus_verify import __version__
from nexus_verify.api import router
from nexus_verify.config import settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title=settings.app_name, version=__version__)
    app.include_router(router)
    return app


app = create_app()


def main() -> None:
    """Run the uvicorn server."""
    uvicorn.run(
        "nexus_verify.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )


if __name__ == "__main__":
    main()
