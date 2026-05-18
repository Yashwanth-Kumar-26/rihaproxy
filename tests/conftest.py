"""Project-wide pytest fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from rihaproxy.gateway.app import create_app
from rihaproxy.storage.db import Storage

pytest_plugins = ["tests.fixtures.conftest"]


@pytest.fixture
def storage(tmp_path) -> Storage:
    data_dir = tmp_path / ".rihaproxy"
    data_dir.mkdir(parents=True, exist_ok=True)
    return Storage(data_dir=data_dir)


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())
