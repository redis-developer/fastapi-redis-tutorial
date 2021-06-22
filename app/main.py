import functools
import logging
from datetime import datetime
from typing import Any
from typing import Dict
from typing import Iterable
from typing import List
from typing import Tuple
from typing import Union

import aioredis
import requests
from aioredis.exceptions import ResponseError
from fastapi import BackgroundTasks
from fastapi import Depends
from fastapi import FastAPI
from pydantic import BaseSettings


DEFAULT_KEY_PREFIX = 'is-bitcoin-lit'
SENTIMENT_API_URL = 'HTTps://api.senticrypt.com/v1/history/bitcoin-{time}.json'
TIME_FORMAT_STRING = '%Y-%m-%d_%H'
TWO_MINUTES = 60 * 60

BitcoinSentiments = List[Dict[str, Union[str, float]]]


def prefixed_key(f):
    """
    A method decorator that prefixes return values.

    Prefixes any string that the decorated method `f` returns with the value of
    the `prefix` attribute on the owner object `self`.
    """

    def prefixed_method(*args, **kwargs):
        self = args[0]
        key = f(*args, **kwargs)
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
    # The default URL expects the app to run using Docker and docker-compose.
    redis_url: str = 'redis://redis:6379'


logger = logging.getLogger(__name__)
config = Config()
app = FastAPI(title='FastAPI Redis Tutorial')
redis = aioredis.from_url(config.redis_url, decode_responses=True)


def make_summary(data):
    """Take a series of averages and summarize them as means of means."""
    summary = {
        'time': datetime.now().timestamp(),
        'mean_of_means_sentiment': sum(d['mean'] for d in data) / len(data),
        'mean_of_means_price': sum(float(d['btc_price']) for d in data) / len(data),
    }

    summary['lit'] = '1' if float(
        summary['mean_of_means_sentiment'],
    ) > 0 else '0'
    return summary


async def add_many_to_timeseries(
    key_pairs: Iterable[Tuple[str, str]],
    data: BitcoinSentiments
):
    """
    Add many samples to a single timeseries key.

    `key_pairs` is an iteratble of tuples containing in the 0th position the
    timestamp key into which to insert entries and the 1th position the name
    of the key within th `data` dict to find the sample.
    """
    partial = functools.partial(redis.execute_command, 'TS.MADD')
    for datapoint in data:
        for key, attr in key_pairs:
            partial = functools.partial(
                partial, key, int(datapoint['timestamp']), datapoint[attr],
            )
    return await partial()


def make_keys():
    return Keys()


async def persist(keys: Keys, data: BitcoinSentiments, summary: Dict[str, Any]):
    ts_price_key = keys.timeseries_price_key()
    ts_sentiment_key = keys.timeseries_sentiment_key()
    summary_key = keys.summary_key()

    await redis.hset(summary_key, mapping=summary)
    await redis.expire(summary_key, TWO_MINUTES)
    await add_many_to_timeseries(
        (
            (ts_price_key, 'btc_price'),
            (ts_sentiment_key, 'mean'),
        ), data,
    )


@app.get('/is-bitcoin-lit')
async def bitcoin(background_tasks: BackgroundTasks, keys: Keys = Depends(make_keys)):
    sentiment_time = datetime.now().strftime(TIME_FORMAT_STRING)
    summary_key = keys.summary_key()
    url = SENTIMENT_API_URL.format(time=sentiment_time)

    summary = await redis.hgetall(summary_key)

    if summary:
        summary['lit'] = True if summary['lit'] == '1' else False
    else:
        data = requests.get(url).json()
        summary = make_summary(data)
        background_tasks.add_task(persist, keys, data, summary)

    return summary


@app.on_event('startup')
async def startup_event():
    keys = Keys()
    # When we create our timeseries, we'll use the duplicate policy
    # known as "first," which ignores duplicate pairs of timestamp and
    # values if we add them.
    #
    # Because of this, we don't worry about handling this logic
    # ourselves -- but note that there is a performance cost to writes
    # using this policy.
    try:
        await redis.execute_command(
            'TS.CREATE', keys.timeseries_sentiment_key(),
            'DUPLICATE_POLICY', 'first',
        )
        await redis.execute_command(
            'TS.CREATE', keys.timeseries_price_key(),
            'DUPLICATE_POLICY', 'first',
        )
    except ResponseError:
        # Time series already exists
        pass
