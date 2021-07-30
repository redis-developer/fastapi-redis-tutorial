# FastAPI Redis Example

This is an example API that demonstrates how to use Redis with FastAPI to build
a fully async web service in Python.

The API is called *IsBitcoinLit*. Readers outside the U.S. who are unfamiliar with
the slang term "lit" might enjoy this [Merriam-Webster
etymology](https://www.merriam-webster.com/words-at-play/lit-meaning-origin#:~:text=Lit%20has%20been%20used%20as,is%20%22exciting%20or%20excellent.%22).

The IsBitcoinLit API tracks Bitcoin sentiment and prices over time, rolling
these up into hourly averages of averages using the [RedisTimeSeries
module](https://oss.redislabs.com/redistimeseries/). You can use the API to get
average Bitcoin price and sentiment for each of the last three hours, with a
quick indication of price and sentiment movement.


## Setup

This project is designed to run as a set of Docker containers. You will need to
[install Docker](https://www.docker.com/) to complete the setup tasks.

First, clone this repo and build the Docker images for the project:

    $ git clone https://github.com/redis-developer/fastapi-redis-tutorial.git
    $ cd fastapi-redis-tutorial
    $ docker-compose build

Running the API involves starting the app server and Redis. You'll do those steps
next!


## Running the API

The `docker-compose.yaml` file in this project configures containers for a Redis
instance with the RedisTimeSeries module, the Python app for the example API,
and a test runner.

Use this command to run all three containers:

    $ docker-compose up

This command starts Redis and the API server and runs the tests.


### Ingesting Price and Sentiment Data

A `/refresh` endpoint exists in the app that ingests the last 24 hours of
Bitcoin price and sentiment data.

The app assumes a scheduler (cron job, Google Cloud Scheduler, etc.) will hit
the `/refresh` endpoint on a regular basis to keep data fresh.

**NOTE** : We can refresh data as often as we want without getting
duplicate data. This is because RedisTimeSeries allows [configuring
rules](https://oss.redislabs.com/redistimeseries/configuration/#duplicate_policy)
to ignore duplicate sample and timestamp pairs.

After you first start the API, use the `/refresh` API to ingest data:

    $ curl -X POST localhost:8080/refresh

Now you can use the `/is-bitcoin-lit` endpoint to see a summary of Bitcoin price
and sentiment data. Continue reading to see how to use that endpoint.

**NOTE**: We've used the free [SentiCrypt](https://senticrypt.com) API to pull
Bitcoin sentiment and price. We are not affiliated with SentiCrypt and this is **in no way**
a recommendation to use the API for crypto price and sentiment tracking in real applications.


### Getting Summary Price and Sentiment Data from the API

Use the `/is-bitcoin-lit` endpoint to get an hourly summary of Bitcoin price and
sentiment data for the last three hours:

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
        }
    ],
    "sentiment_direction": "rising",
    "price_direction": "rising"
    }
```

As you can see, the response includes the key `hourly_average_of_averages`. This
key contains hourly averages derived from the Bitcoin sentiment API's data,
which is itself averaged over 30-second periods. (Thus, these are *averages of
averages*.)

The API also returns the *direction* that the price and sentiment are moving.
The directions are:

Value  | Meaning
---------|----------
Rising | The price has risen over the past three hours.
Falling | The price has fallen over the past three hours.
Neutral | The price stayed the same for three hours (unlikely!)

So, *is Bitcoin lit* in this example? Yes, it's lit: the price and sentiment are
rising. See how that works?


### Running Tests

You can run the app's test suite using docker-compose:

    $ docker-compose up test
