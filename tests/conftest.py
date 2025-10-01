import os
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("SUPABASE_DISABLED", "1")
os.environ.setdefault("SUPABASE_STORAGE_LOCAL_DIR", ".local_storage")


@pytest.fixture(scope="session")
def client() -> TestClient:
    # lazy import after env configured
    from src.main import create_app

    app = create_app()
    return TestClient(app)


@pytest.fixture()
def auth_header() -> dict[str, str]:
    # any token is accepted in disabled mode
    return {"Authorization": "Bearer test-token"}

