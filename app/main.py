import logging

from aiotestspeed.aio import Speedtest
from fastapi import FastAPI

logger = logging.getLogger(__name__)
app = FastAPI()


@app.get('/speedtest')
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
