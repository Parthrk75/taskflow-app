import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")

    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_NAME = os.getenv("DB_NAME", "tasksdb")
    DB_USER = os.getenv("DB_USER", "taskuser")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "taskpass")

    APP_ENV = os.getenv("APP_ENV", "development")
    APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
    SEED_DATA = os.getenv("SEED_DATA", "true").lower() == "true"
    PER_PAGE = 8
