from pydantic import BaseSettings


class Config(BaseSettings):
    redis_host: str = "redis"
    redis_port: str = "6379"
    redis_password: str = "password"


config = Config()
