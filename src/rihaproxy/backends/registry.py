"""
Provider Registry Module
Dynamically loads and registers backend adapters.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Type

from rihaproxy.backends.base import BackendAdapter
import rihaproxy.backends
import structlog

logger = structlog.get_logger()

# Global registry dictionary
PROVIDER_REGISTRY: dict[str, Type[BackendAdapter]] = {}

def register_adapter(name: str, adapter_class: Type[BackendAdapter]) -> None:
    """Register an adapter class with a specific name."""
    PROVIDER_REGISTRY[name.lower()] = adapter_class
    logger.debug("adapter_registered", provider=name)

def register_aliases(adapter_class: Type[BackendAdapter], aliases: list[str]) -> None:
    """Register an adapter class with multiple alias names."""
    for alias in aliases:
        register_adapter(alias, adapter_class)

def discover_adapters() -> None:
    """
    Dynamically discover and load all adapters in the rihaproxy.backends package.
    """
    import os
    from pathlib import Path
    
    backends_dir = Path(__file__).parent
    
    # Also load opencode adapters specifically since they have a different structure
    opencode_dir = backends_dir / "opencode" / "adapters"
    if opencode_dir.exists():
        for py_file in opencode_dir.glob("*.py"):
            if py_file.name == "__init__.py":
                continue
            module_name = f"rihaproxy.backends.opencode.adapters.{py_file.stem}"
            _load_module_adapters(module_name)
    
    # Standard adapters
    for item in backends_dir.iterdir():
        if item.is_dir() and (item / "adapter.py").exists():
            module_name = f"rihaproxy.backends.{item.name}.adapter"
            _load_module_adapters(module_name)

def _load_module_adapters(module_name: str) -> None:
    """Helper to load all adapters from a specific module."""
    try:
        module = importlib.import_module(module_name)
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, BackendAdapter) and attr is not BackendAdapter:
                if hasattr(attr, "provider_name") and attr.provider_name:
                    register_adapter(attr.provider_name, attr)
                if hasattr(attr, "provider_aliases") and attr.provider_aliases:
                    register_aliases(attr, attr.provider_aliases)
    except Exception as e:
        logger.warning("failed_to_load_adapter", module=module_name, error=str(e))

def get_adapter_class(name: str) -> Type[BackendAdapter] | None:
    """Get the adapter class for a given provider name."""
    # Ensure adapters are discovered
    if not PROVIDER_REGISTRY:
        discover_adapters()
    return PROVIDER_REGISTRY.get(name.lower())

def get_all_providers() -> list[str]:
    """Get a list of all registered provider names."""
    if not PROVIDER_REGISTRY:
        discover_adapters()
    return list(PROVIDER_REGISTRY.keys())
