"""FastAPI application factory, independent of the customer/admin clients."""
from src.api import create_app

__all__ = ["create_app"]
