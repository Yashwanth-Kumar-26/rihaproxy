"""
RihaProxy — Universal AI Gateway
One key, 40+ providers, auto-fallback.
"""

__version__ = "0.1.0"
__author__ = "RihaProxy Team"

from rihaproxy.config import Settings
from rihaproxy.gateway.app import create_app

__all__ = ["create_app", "Settings", "__version__"]