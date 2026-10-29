import os
from pathlib import Path

import pytest
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class TestSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    test_database_url: str


# Point the app at the test database before anything imports app.config.
TEST_DATABASE_URL = TestSettings().test_database_url
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from alembic import command  # noqa: E402
from app.db import engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.attributes["database_url"] = TEST_DATABASE_URL
    command.upgrade(config, "head")


@pytest.fixture(autouse=True)
def clean_expenses():
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE expense_shares, expenses RESTART IDENTITY"))


@pytest.fixture
def client():
    return TestClient(app)
