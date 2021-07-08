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

The app assumes a scheduler (cron job, Cloud scheduler, etc.) will hit the `/refresh` endpoint in the app to trigger ingesting Bitcoin price and sentiment data on a regular basis.

Use this API to ingest data when you're playing with the API:

    $
