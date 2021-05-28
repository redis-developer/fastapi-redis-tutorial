from typing import Generator

import pytest
from fastapi.testclient import TestClient
from redis.utils import from_url

from app.main import app
from app.main import config


@pytest.fixture(scope='module')
def client() -> Generator:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope='module')
def redis() -> Generator:
    yield from_url(config.redis_url)
