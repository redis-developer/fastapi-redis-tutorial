import json
import logging
import socket

import aioredis
from aiotestspeed.aio import Speedtest
from fastapi import FastAPI
from pydantic import BaseSettings


SPEEDTEST_KEY = 'speedtest:{ip}'


class Config(BaseSettings):
    redis_url: str = 'redis://redis:6379'


logger = logging.getLogger(__name__)
config = Config()
app = FastAPI(title='FastAPI Redis Tutorial')
redis = aioredis.from_url(config.redis_url)


def get_cache_key():
    hostname = socket.gethostname()
    ip = socket.gethostbyname(hostname)
    return SPEEDTEST_KEY.format(ip=ip)


@app.get('/speedtest')
async def speedtest():
    logger.debug('Running speedtest')
    key = get_cache_key()

    found = await redis.get(key)
    if found:
        data = json.loads(found)
    else:
        s: Speedtest = await Speedtest()
        await s.get_best_server()
        await s.download()
        await s.upload()

        data = {
            'ping_ms': s.results.ping,
            'download_mbps': s.results.download / 1000.0 / 1000.0 / 1,
            'upload_mbps': s.results.upload / 1000.0 / 1000.0 / 1,
        }
        await redis.set(key, json.dumps(data), ex=30)

    return data
