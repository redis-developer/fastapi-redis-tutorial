from typing import Generator

import pytest
from fastapi.testclient import TestClient

from app.core.application import create_api


@pytest.fixture(scope='module')
def client() -> Generator:
    api = create_api()
    with TestClient(api) as c:
        yield c
