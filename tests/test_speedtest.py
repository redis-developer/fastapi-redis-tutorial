import json

from fastapi.testclient import TestClient
from redis import Redis


def test_speedtest(client: TestClient):
    res = client.get('/speedtest')
    json = res.json()

    assert res.status_code == 200

    for field in ('ping_ms', 'download_mbps', 'upload_mbps'):
        assert field in json


def test_speedtest_cache(client: TestClient, redis: Redis):
    # prime the cache
    client.get('/speedtest')

    cached = redis.get('speedtest-cache:app.main.speedtest()')
    assert cached is not None
    data = json.loads(cached)

    for field in ('ping_ms', 'download_mbps', 'upload_mbps'):
        assert field in data
