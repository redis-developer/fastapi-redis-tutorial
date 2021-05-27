from fastapi.testclient import TestClient


def test_speedtest(client: TestClient):
    res = client.get('/speedtest')
    json = res.json()

    assert res.status_code == 200

    for field in ('ping_ms', 'download_mbps', 'upload_mbps'):
        assert field in json
