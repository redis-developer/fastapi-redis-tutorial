from fastapi import FastAPI

from app.api.endpoints import speedtest


def create_api():
    api = FastAPI()

    api.include_router(speedtest.router)

    return api
