import functools
import json
import logging
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Dict
from typing import Iterable
from typing import List
from typing import Tuple
from typing import Union

import aioredis
import httpx
from aioredis.exceptions import ResponseError
from fastapi import BackgroundTasks
from fastapi import Depends
from fastapi import FastAPI
from pydantic import BaseSettings

DEFAULT_KEY_PREFIX = 'is-bitcoin-lit'
SENTIMENT_API_URL = 'https://api.senticrypt.com/v1/bitcoin.json'
TWO_MINUTES = 60 + 60
HOURLY_BUCKET = '3600000'

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
        """A time series containing 30-second snapshots of BTC sentiment."""
        return f'sentiment:mean:30s'

    @prefixed_key
    def timeseries_price_key(self) -> str:
        """A time series containing 30-second snapshots of BTC price."""
        return f'price:mean:30s'

    @prefixed_key
    def cache_key(self) -> str:
        return f'cache'


class Config(BaseSettings):
    # The default URL expects the app to run using Docker and docker-compose.
    redis_url: str = 'redis://redis:6379'


log = logging.getLogger(__name__)
config = Config()
app = FastAPI(title='FastAPI Redis Tutorial')
redis = aioredis.from_url(config.redis_url, decode_responses=True)


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
        for timeseries_key, sample_key in key_pairs:
            partial = functools.partial(
                partial, timeseries_key, int(
                    float(datapoint['timestamp']) * 1000,
                ),
                datapoint[sample_key],
            )
    return await partial()


def make_keys():
    return Keys()


async def persist(keys: Keys, data: BitcoinSentiments):
    ts_sentiment_key = keys.timeseries_sentiment_key()
    ts_price_key = keys.timeseries_price_key()
    await add_many_to_timeseries(
        (
            (ts_price_key, 'btc_price'),
            (ts_sentiment_key, 'mean'),
        ), data,
    )


async def get_hourly_average(ts_key: str, top_of_the_hour: int):
    response = await redis.execute_command(
        'TS.RANGE', ts_key, top_of_the_hour, '+',
        'AGGREGATION', 'avg', HOURLY_BUCKET,
    )
    # Returns a list of the structure [timestamp, average].
    return response


def datetime_parser(dct):
    for k, v in dct.items():
        if isinstance(v, str) and v.endswith('+00:00'):
            try:
                dct[k] = datetime.datetime.fromisoformat(v)
            except:
                pass
    return dct


async def get_cache(keys: Keys):
    current_hour_cache_key = keys.cache_key()
    current_hour_stats = await redis.get(current_hour_cache_key)

    if current_hour_stats:
        return json.loads(current_hour_stats, object_hook=datetime_parser)


async def set_cache(data, keys: Keys):
    def serialize_dates(v):
        return v.isoformat() if isinstance(v, datetime) else v

    await redis.set(
        keys.cache_key(),
        json.dumps(data, default=serialize_dates),
        ex=TWO_MINUTES,
    )


def get_direction(last_three_hours, key: str):
    if last_three_hours[0][key] < last_three_hours[-1][key]:
        return 'rising'
    elif last_three_hours[0][key] > last_three_hours[-1][key]:
        return 'falling'
    else:
        return 'flat'


def now():
    """Wrap call to utcnow, so that we can mock this function in tests."""
    return datetime.utcnow()


async def calculate_three_hours_of_data(keys: Keys) -> Dict[str, str]:
    sentiment_key = keys.timeseries_sentiment_key()
    price_key = keys.timeseries_price_key()
    three_hours_ago_ms = int((now() - timedelta(hours=3)).timestamp() * 1000)

    sentiment = await get_hourly_average(sentiment_key, three_hours_ago_ms)
    price = await get_hourly_average(price_key, three_hours_ago_ms)

    last_three_hours = [{
        'price': data[0][1], 'sentiment': data[1][1],
        'time': datetime.fromtimestamp(data[0][0] / 1000, tz=timezone.utc),
    }
        for data in zip(price, sentiment)]

    return {
        'hourly_average_of_averages': last_three_hours,
        'sentiment_direction': get_direction(last_three_hours, 'sentiment'),
        'price_direction': get_direction(last_three_hours, 'price'),
    }


@app.post('/refresh')
async def refresh(background_tasks: BackgroundTasks, keys: Keys = Depends(make_keys)):
    async with httpx.AsyncClient() as client:
        data = await client.get(SENTIMENT_API_URL)
    await persist(keys, data.json())
    data = await calculate_three_hours_of_data(keys)
    background_tasks.add_task(set_cache, data, keys)


@app.get('/is-bitcoin-lit')
async def bitcoin(background_tasks: BackgroundTasks, keys: Keys = Depends(make_keys)):
    data = await get_cache(keys)

    if not data:
        data = await calculate_three_hours_of_data(keys)
        background_tasks.add_task(set_cache, data, keys)

    return data


async def make_timeseries(key):
    """
    Create a timeseries with the Redis key `key`.

    We'll use the duplicate policy known as "first," which ignores
    duplicate pairs of timestamp and values if we add them.

    Because of this, we don't worry about handling this logic
    ourselves -- but note that there is a performance cost to writes
    using this policy.
    """
    try:
        await redis.execute_command(
            'TS.CREATE', key,
            'DUPLICATE_POLICY', 'first',
        )
    except ResponseError as e:
        # Time series probably already exists
        log.info('Could not create timeseries %s, error: %s', key, e)


async def initialize_redis(keys: Keys):
    await make_timeseries(keys.timeseries_sentiment_key())
    await make_timeseries(keys.timeseries_price_key())


@app.on_event('startup')
async def startup_event():
    keys = Keys()
    await initialize_redis(keys)
