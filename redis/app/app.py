from google.cloud import bigquery
from fastapi import FastAPI, Depends
import redis
import json

app = FastAPI()
client = bigquery.Client()
redis_client = redis.Redis(host='localhost', port=6379, db=0)  # Adjust connection settings as needed


def cache_query_results(query: str):
    # Call redis with cache key
    cache_key = f"query:{query}"
    cached_result = redis_client.get(cache_key)

    # 1. If we already have the result
    if cached_result:
        return json.loads(cached_result)

    # 2. Else cache miss => pull latest data and refresh cache
    query_job = client.query(query)
    results = list(query_job.result())
    # Cache the results for 1 hour (3600 seconds)
    redis_client.set(cache_key, json.dumps([dict(row) for row in results]), ex=3600)
    return results


@app.get("/features")
async def get_features():
    bq_query = """
    SELECT feature_name, AVG(feature_value) AS feature_avg
    FROM `your_project.your_dataset.your_table`
    GROUP BY feature_name
    """
    redis_query = """
    SELECT feature_name, AVG(feature_value) AS feature_avg
    FROM `your_project.your_dataset.your_table`
    GROUP BY feature_name
    """
    results = cache_query_results(query)
    return {row["feature_name"]: row["feature_avg"] for row in results}
