"""Configuration module for the application."""

from datetime import timedelta
from os import getenv, environ

from models.enums import NoHarmENV


def is_lambda_environment() -> bool:
    """Return True when running inside AWS Lambda."""
    return getenv("AWS_LAMBDA_FUNCTION_NAME") is not None


def build_database_url() -> str:
    """
    Build PostgreSQL connection string from separated environment variables.

    Expected env vars:
    - DB_HOST
    - DB_PORT
    - DB_NAME
    - DB_USER
    - DB_PASSWORD
    """
    db_host = environ["DB_HOST"]
    db_port = getenv("DB_PORT", "5432")
    db_name = environ["DB_NAME"]
    db_user = environ["DB_USER"]
    db_password = environ["DB_PASSWORD"]

    return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"


def get_database_url() -> str:
    """
    Resolve the main database connection string.

    Priority:
    1. POSTGRESQL_CONNECTION_STRING
    2. POTGRESQL_CONNECTION_STRING, old typo kept for compatibility
    3. DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD
    4. Local docker-compose fallback only outside Lambda
    """
    connection_string = (
        getenv("POSTGRESQL_CONNECTION_STRING")
        or getenv("POTGRESQL_CONNECTION_STRING")
    )

    if connection_string:
        return connection_string

    if getenv("DB_HOST"):
        return build_database_url()

    if is_lambda_environment():
        raise RuntimeError(
            "Database configuration is missing. "
            "Set POSTGRESQL_CONNECTION_STRING or DB_HOST, DB_NAME, DB_USER and DB_PASSWORD."
        )

    return "postgresql://postgres@db/noharm"


class Config:
    """Configuration class for the application."""

    VERSION = "v6.15-beta"
    FRONTEND_VERSION = "5.1.6"

    ENV = getenv("ENV") or NoHarmENV.DEVELOPMENT.value

    SECRET_KEY = getenv("SECRET_KEY") or "secret_key"
    ENCRYPTION_KEY = getenv("ENCRYPTION_KEY") or None
    API_KEY = getenv("API_KEY") or ""

    SELF_API_URL = getenv("SELF_API_URL") or ""
    APP_URL = getenv("APP_URL")
    APP_DOMAIN = getenv("APP_DOMAIN") or "localhost"

    POSTGRESQL_CONNECTION_STRING = get_database_url()

    POTGRESQL_CONNECTION_STRING = POSTGRESQL_CONNECTION_STRING

    REPORT_CONNECTION_STRING = (
        getenv("REPORT_CONNECTION_STRING")
        or POSTGRESQL_CONNECTION_STRING
    )

    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        minutes=int(getenv("JWT_ACCESS_TOKEN_EXPIRES", "20"))
    )

    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        days=int(getenv("JWT_REFRESH_TOKEN_EXPIRES", "30"))
    )

    MAIL_USERNAME = getenv("MAIL_USERNAME") or "user@gmail.com"
    MAIL_PASSWORD = getenv("MAIL_PASSWORD") or "password"
    MAIL_SENDER = getenv("MAIL_SENDER") or "user@gmail.com"
    MAIL_HOST = getenv("MAIL_HOST") or "localhost"

    NIFI_BUCKET_NAME = getenv("NIFI_BUCKET_NAME") or ""
    NIFI_SQS_QUEUE_REGION = getenv("NIFI_SQS_QUEUE_REGION") or ""
    NIFI_LOG_GROUP_NAME = getenv("NIFI_LOG_GROUP_NAME") or ""

    CACHE_BUCKET_NAME = getenv("CACHE_BUCKET_NAME") or ""
    CACHE_BUCKET_ID = getenv("CACHE_BUCKET_ID") or ""
    CACHE_BUCKET_KEY = getenv("CACHE_BUCKET_KEY") or ""

    ODOO_API_DB = getenv("ODOO_API_DB") or ""
    ODOO_API_KEY = getenv("ODOO_API_KEY") or ""
    ODOO_API_URL = getenv("ODOO_API_URL") or ""
    ODOO_API_USER = getenv("ODOO_API_USER") or ""

    OPEN_AI_API_ENDPOINT = getenv("OPEN_AI_API_ENDPOINT") or ""
    OPEN_AI_API_KEY = getenv("OPEN_AI_API_KEY") or ""
    OPEN_AI_API_VERSION = getenv("OPEN_AI_API_VERSION") or ""
    OPEN_AI_API_MODEL = getenv("OPEN_AI_API_MODEL") or ""

    MARITACA_API_KEY = getenv("MARITACA_API_KEY") or ""

    REDIS_HOST = getenv("REDIS_HOST") or ""
    REDIS_PORT = getenv("REDIS_PORT") or ""

    SCORES_FUNCTION_NAME = getenv("SCORES_FUNCTION_NAME", "")
    BACKEND_FUNCTION_NAME = getenv("BACKEND_FUNCTION_NAME", "")

    SERVICE_INFERENCE = getenv("SERVICE_INFERENCE", None)

    FEATURE_CONCILIATION_ALGORITHM = getenv(
        "FEATURE_CONCILIATION_ALGORITHM",
        "FUZZY"
    )

    SCHEDULER_ENABLED = getenv("SCHEDULER_ENABLED", "false").lower() == "true"
    SCHEDULER_INTERVAL_MINUTES = int(getenv("SCHEDULER_INTERVAL_MINUTES", "15"))
    SCHEDULER_JOB_TIMEOUT_SECONDS = int(getenv("SCHEDULER_JOB_TIMEOUT_SECONDS", "300"))


class TestConfig(Config):
    TESTING = True
    DEBUG = True

    CORS_ORIGINS = [
        Config.MAIL_HOST,
        "http://localhost:3000",
    ]

    SQLALCHEMY_DATABASE_URI = Config.POSTGRESQL_CONNECTION_STRING

    SQLALCHEMY_BINDS = {
        "report": Config.REPORT_CONNECTION_STRING
    }