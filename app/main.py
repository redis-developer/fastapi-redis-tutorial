import logging

from aiotestspeed.aio import Speedtest
from fastapi import FastAPI
from fastapi import Request
from fastapi import Response
from fastapi_redis_cache import cache
from fastapi_redis_cache import FastApiRedisCache
from pydantic import BaseSettings


class Config(BaseSettings):
    redis_url: str = 'redis://redis:6379'


logger = logging.getLogger(__name__)
config = Config()
app = FastAPI(title='FastAPI Redis Cache Example')


@app.on_event('startup')
def startup():
    redis_cache = FastApiRedisCache()
    redis_cache.init(
        host_url=config.redis_url,
        prefix='speedtest-cache',
        response_header='X-Speedtest-Cache',
        ignore_arg_types=[Request, Response],
    )


@app.get('/speedtest')
@cache(expire=30)
async def speedtest():
    logger.debug('Running speedtest')
    s: Speedtest = await Speedtest()
    await s.get_best_server()
    await s.download()
    await s.upload()
    return {
        'ping_ms': s.results.ping,
        'download_mbps': s.results.download / 1000.0 / 1000.0 / 1,
        'upload_mbps': s.results.upload / 1000.0 / 1000.0 / 1,
    }
    return s
