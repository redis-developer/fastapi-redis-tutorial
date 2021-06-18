import functools
import logging
from datetime import datetime
from typing import Dict
from typing import Iterable
from typing import List
from typing import Tuple
from typing import Union

import aioredis
import requests
from aioredis.exceptions import ResponseError
from fastapi import Depends
from fastapi import FastAPI
from pydantic import BaseSettings


DEFAULT_KEY_PREFIX = 'is-bitcoin-lit'
SENTIMENT_API_URL = 'HTTps://api.senticrypt.com/v1/history/bitcoin-{time}.json'
TIME_FORMAT_STRING = '%Y-%m-%d_%H'


def prefixed_key(f):
    """
    A method decorator that prefixes return values.
    Prefixes any string that the decorated method `f` returns with the value of
    the `prefix` attribute on the owner object `self`.
    """

    def prefixed_method(self, *args, **kwargs):
        key = f(self, *args, **kwargs)
        return f'{self.prefix}:{key}'

    return prefixed_method


class Keys:
    """Methods to generate key names for Redis data structures."""

    def __init__(self, prefix: str = DEFAULT_KEY_PREFIX):
        self.prefix = prefix

    @prefixed_key
    def timeseries_sentiment_key(self) -> str:
        return f'sentiment:mean'

    @prefixed_key
    def timeseries_price_key(self) -> str:
        return f'price:mean'

    @prefixed_key
    def summary_key(self) -> str:
        return f'summary:hourly'


class Config(BaseSettings):
    redis_url: str = 'redis://redis:6379'


logger = logging.getLogger(__name__)
config = Config()
app = FastAPI(title='FastAPI Redis Tutorial')
redis = aioredis.from_url(config.redis_url, decode_responses=True)


def make_summary(data):
    """Take a series of averages and summarize them as means of means."""
    return {
        'time': datetime.now().timestamp(),
        'mean_of_means_sentiment': sum(d['mean'] for d in data) / len(data),
        'mean_of_means_price': sum(float(d['btc_price']) for d in data) / len(data),
    }


async def add_many_to_timeseries(
    key_pairs: Iterable[Tuple[str, str]],
    data: List[Dict[str, Union[str, float]]]
):
    """
    Add many samples to a single timeseries key.

    `key_pairs` is an iteratble of tuples containing in the 0th position the
    timestamp key into which to insert entries and the 1th position the name
    of the key within th e`data` dict to find the sample.
    """
    partial = functools.partial(redis.execute_command, 'TS.MADD')
    for datapoint in data:
        for key, attr in key_pairs:
            partial = functools.partial(
                partial, key, datapoint['timestamp'], datapoint[attr],
            )
    return await partial()


def make_keys():
    return Keys()


@app.get('/is-bitcoin-lit')
async def bitcoin(keys: Keys = Depends(make_keys)):
    sentiment_time = datetime.now().strftime(TIME_FORMAT_STRING)
    summary_key = keys.summary_key()
    ts_price_key = keys.timeseries_price_key()
    ts_sentiment_key = keys.timeseries_sentiment_key()
    url = SENTIMENT_API_URL.format(time=sentiment_time)

    summary = await redis.hgetall(summary_key)

    if not summary:
        # TODO: Only add timeseries data that we don't already have -- how?
        data = requests.get(url).json()
        summary = make_summary(data)
        await redis.hset(summary_key, mapping=summary)
        await redis.expire(summary_key, 60)
        await add_many_to_timeseries(
            (
                (ts_price_key, 'btc_price'),
                (ts_sentiment_key, 'mean'),
            ), data,
        )

    return summary


@app.on_event('startup')
async def startup_event(keys: Keys = Depends(make_keys)):
    try:
        redis.execute_command('TS.CREATE', keys.timeseries_sentiment_key())
        redis.execute_command('TS.CREATE', keys.timeseries_price_key())
    except ResponseError:
        # Time series already exists
        pass
