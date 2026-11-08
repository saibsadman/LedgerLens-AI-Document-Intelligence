import os
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///./data/test_docintel.sqlite3"
os.environ["STORAGE_PATH"] = "./data/test_uploads"
os.environ["USE_CELERY"] = "false"
os.environ.pop("OPENAI_API_KEY", None)

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    upload_path = Path("./data/test_uploads")
    upload_path.mkdir(parents=True, exist_ok=True)
    yield
    for file in upload_path.glob("*"):
        if file.is_file():
            file.unlink()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
