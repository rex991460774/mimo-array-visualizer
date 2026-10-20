"""HTTP server: FastAPI application serving the API and the web client."""

from .app import create_app

__all__ = ["create_app"]
