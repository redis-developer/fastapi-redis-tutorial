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
import requests
from aioredis.exceptions import ResponseError
from fastapi import Depends
from fastapi import FastAPI
from pydantic import BaseSettings


DEFAULT_KEY_PREFIX = 'is-bitcoin-lit'
SENTIMENT_API_URL = 'https://api.senticrypt.com/v1/bitcoin.json'
TWO_MINUTES = 60 * 60
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
    def timeseries_30_second_sentiment_key(self) -> str:
        """A time series containing 30-second snapshots of BTC sentiment."""
        return f'sentiment:mean:30s'

    @prefixed_key
    def timeseries_1_hour_sentiment_key(self) -> str:
        """A time series containing 1-hour snapshots of BTC sentiment."""
        return f'sentiment:mean:1h'

    @prefixed_key
    def timeseries_30_second_price_key(self) -> str:
        """A time series containing 30-second snapshots of BTC price."""
        return f'price:mean:30s'

    @prefixed_key
    def timeseries_1_hour_price_key(self) -> str:
        """A time series containing 1-hour snapshots of BTC price."""
        return f'price:mean:1h'

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
    ts_sentiment_key = keys.timeseries_30_second_sentiment_key()
    ts_price_key = keys.timeseries_30_second_price_key()
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
    # Return the average without the timestamp. The response is a list
    # of the structure [timestamp, average].
    print(response)
    return response[0][1]


async def get_current_hour_data(keys):
    ts_sentiment_key = keys.timeseries_30_second_sentiment_key()
    ts_price_key = keys.timeseries_30_second_price_key()
    top_of_the_hour = int(
        datetime.utcnow().replace(
            minute=0,
            second=0,
            microsecond=0,
        ).timestamp() * 1000,
    )
    current_hour_avg_sentiment = await get_hourly_average(ts_sentiment_key, top_of_the_hour)
    current_hour_avg_price = await get_hourly_average(ts_price_key, top_of_the_hour)

    return {
        'time': datetime.fromtimestamp(top_of_the_hour / 1000, tz=timezone.utc).isoformat(),
        'price': current_hour_avg_price,
        'sentiment': current_hour_avg_sentiment,
    }


async def get_current_hour_cache(keys: Keys):
    current_hour_cache_key = keys.cache_key()
    current_hour_stats = await redis.get(current_hour_cache_key)

    if current_hour_stats:
        return json.loads(current_hour_stats)


async def refresh_hourly_cache(keys: Keys):
    current_hour_stats = await get_current_hour_data(keys)
    await redis.set(
        keys.cache_key(), json.dumps(current_hour_stats),
        ex=TWO_MINUTES,
    )
    return current_hour_stats


async def set_current_hour_cache(keys: Keys):
    # First, scrape the sentiment API and persist the data.
    data = requests.get(SENTIMENT_API_URL).json()
    await persist(keys, data)

    # Now that we've ingested raw sentiment data, aggregate it for the current
    # hour and cache the result.
    return await refresh_hourly_cache(keys)


@app.get('/refresh')
async def bitcoin(keys: Keys = Depends(make_keys)):
    data = requests.get(SENTIMENT_API_URL).json()
    await persist(keys, data)
    await refresh_hourly_cache(keys)


@app.get('/is-bitcoin-lit')
async def bitcoin(keys: Keys = Depends(make_keys)):
    now = datetime.utcnow()
    sentiment_1h_key = keys.timeseries_1_hour_sentiment_key()
    price_1h_key = keys.timeseries_1_hour_price_key()
    current_hour_stats_cached = await get_current_hour_cache(keys)

    if not current_hour_stats_cached:
        current_hour_stats_cached = await set_current_hour_cache(keys)

    three_hours_ago_ms = int((now - timedelta(hours=3)).timestamp() * 1000)
    sentiment = await redis.execute_command('TS.RANGE', sentiment_1h_key, three_hours_ago_ms, '+')
    price = await redis.execute_command('TS.RANGE', price_1h_key, three_hours_ago_ms, '+')
    past_hours = [{
        'price': data[0][1], 'sentiment': data[1][1],
        'time': datetime.fromtimestamp(data[0][0] / 1000, tz=timezone.utc),
    }
        for data in zip(price, sentiment)]
    return past_hours + [current_hour_stats_cached]


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


async def make_rule(src: str, dest: str):
    """
    Create a compaction rule from timeseries at `str` to `dest`.

    This rule aggregates metrics using 'avg' into hourly buckets.
    """
    try:
        await redis.execute_command(
            'TS.CREATERULE', src, dest, 'AGGREGATION', 'avg', HOURLY_BUCKET,
        )
    except ResponseError as e:
        # Rule probably already exists.
        log.info(
            'Could not create timeseries rule (from %s to %s), error: %s', src, dest, e,
        )


async def initialize_redis(keys: Keys):
    ts_30_sec_sentiment = keys.timeseries_30_second_sentiment_key()
    ts_1_hour_sentiment = keys.timeseries_1_hour_sentiment_key()
    ts_30_sec_price = keys.timeseries_30_second_price_key()
    ts_1_hour_price = keys.timeseries_1_hour_price_key()

    await make_timeseries(ts_30_sec_sentiment)
    await make_timeseries(ts_1_hour_sentiment)
    await make_timeseries(ts_30_sec_price)
    await make_timeseries(ts_1_hour_price)

    await make_rule(ts_30_sec_sentiment, ts_1_hour_sentiment)
    await make_rule(ts_30_sec_price, ts_1_hour_price)


@app.on_event('startup')
async def startup_event():
    keys = Keys()
    await initialize_redis(keys)
