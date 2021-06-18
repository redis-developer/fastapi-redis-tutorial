import functools
import json
import logging
from datetime import datetime

import aioredis
import requests
from aioredis.exceptions import ResponseError
from fastapi import FastAPI
from pydantic import BaseSettings


TIMESERIES_KEY = 'is-bitcoin-lit:sentiment:mean:{time}'
SUMMARY_KEY = 'is-bitcoin-lit:summary:hourly:{time}'
SENTIMENT_API_URL = 'https://api.senticrypt.com/v1/history/bitcoin-{time}.json'
TIME_FORMAT_STRING = '%Y-%m-%d_%H'


class Config(BaseSettings):
    redis_url: str = 'redis://redis:6379'


logger = logging.getLogger(__name__)
config = Config()
app = FastAPI(title='FastAPI Redis Tutorial')
redis = aioredis.from_url(config.redis_url, decode_responses=True)


def make_summary(data):
    return {
        'time': datetime.now().timestamp(),
        'mean_sentiment': sum(d['mean'] for d in data) / len(data),
    }


@app.get('/is-bitcoin-lit')
async def bitcoin():
    sentiment_time = datetime.now().strftime(TIME_FORMAT_STRING)
    summary_key = SUMMARY_KEY.format(time=sentiment_time)
    ts_key = TIMESERIES_KEY.format(time=sentiment_time)
    url = SENTIMENT_API_URL.format(time=sentiment_time)

    summary = await redis.hgetall(summary_key)

    if not summary:
        # TODO: Only add timeseries data that we don't already have -- how?
        data = requests.get(url).json()
        summary = make_summary(data)
        await redis.hset(summary_key, mapping=summary)
        await redis.expire(summary_key, 60)
        partial = functools.partial(redis.execute_command, 'TS.MADD', ts_key)
        for datapoint in data:
            partial = functools.partial(
                partial, datapoint['timestamp'], datapoint['mean'],
            )
        await partial()

    return summary


@app.on_event('startup')
async def startup_event():
    try:
        redis.execute_command('TS.CREATE', TIMESERIES_KEY)
    except ResponseError:
        # Time series already exists
        pass
