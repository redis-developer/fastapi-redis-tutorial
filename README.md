# FastAPI Redis Example

This is an example API that demonstrates how to use Redis, RedisTimeSeries, and
FastAPI together.

The service tracks Bitcoin sentiment and prices over time, rolling these up into
hourly averages using RedisTimeSeries. You can use the API to get average
Bitcoin price and sentiment for each of the last three hours, with a quick
indication of price and sentiment movement.


## Setup

To run this service, you'll need Docker. First, clone the repo and
install the dependencies:

    $ git clone https://github.com/redis-developer/fastapi-redis-tutorial.git
    $ cd fastapi-redis-tutorial
    $ docker-compose build


## Running the API

The `docker-compose.yaml` file in this project configures a Redis instance with
the RedisTimeSeries module, the Python app for the example API, and a test
runner.

Use this command to run the app:

    $ docker-compose up

This command starts Redis and the API server.


### Ingesting Price and Sentiment Data

The app assumes a scheduler (cron job, Cloud scheduler, etc.) will hit the
`/refresh` endpoint in the app to ingest the last 24 hours of Bitcoin price and
sentiment data on a regular basis.

**NOTE** : We can refresh more than once every 24 hours without getting
*duplicate data in our time series. This is because RedisTimeSeries allows
*configuring rules to ignore duplicate sample and timestamp pairs.

Use this API to ingest data when you're playing with the API:

    $ curl -X POST localhost:8080/refresh

After you've ingested data, you can request the `/is-bitcoin-lit` endpoint to
see a summary of Bitcoin price and sentiment data. Continue reading to see how
to use that endpoint.

**NOTE**: We've used the free [SentiCrypt](https://senticrypt.com) API to pull
Bitcoin sentiment and price.


### Getting Summary Price and Sentiment Data from the API

Use the `/is-bitcoin-lit` endpoint to get an hourly summary of Bitcoin price and sentiment data for the last three hours:

    $ curl localhost:8080/is-bitcoin-lit | jq

```json
    {
    "hourly_average_of_averages": [
        {
        "price": "32928.345",
        "sentiment": "0.22",
        "time": "2021-07-08T17:00:00+00:00"
        },
        {
        "price": "32834.2910891089",
        "sentiment": "0.224257425742574",
        "time": "2021-07-08T18:00:00+00:00"
        },
        {
        "price": "32871.3406666667",
        "sentiment": "0.208666666666667",
        "time": "2021-07-08T19:00:00+00:00"
        },
        {
        "price": "32937.7355952381",
        "sentiment": "0.221547619047619",
        "time": "2021-07-08T20:00:00+00:00"
        }
    ],
    "sentiment_direction": "rising",
    "price_direction": "rising"
    }
```

As you can see, the response includes the key `hourly_average_of_averages`. This key contains hourly averages derived from the Bitcoin sentiment API's data, which is itself averaged over 30-second periods. (Thus, these are *averages of averages*.)

The API also returns the *direction* that the price and sentiment are moving. The directions are:

Value  | Meaning
---------|----------
Rising | The price has risen over the past three hours.
Falling | The price has fallen over the past three hours.
Neutral | The price stayed the same for three hours (unlikely!)


### Running Tests

You can run the app's test suite using docker-compose:

    $ docker-compose up test
