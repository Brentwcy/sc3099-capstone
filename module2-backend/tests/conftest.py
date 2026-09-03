import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.rate_limit import RateLimitPolicy, get_rate_limiter
from app.main import app


class InMemoryRateLimiter:
    def __init__(self):
        self.attempts: dict[tuple[str, str], int] = {}

    def consume(self, *, policy: RateLimitPolicy, identifier: str) -> int | None:
        key = (policy.name, identifier)
        attempts = self.attempts.get(key, 0) + 1
        self.attempts[key] = attempts
        return policy.window_seconds if attempts > policy.limit else None


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def client(db_session):
    rate_limiter = InMemoryRateLimiter()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_rate_limiter] = lambda: rate_limiter
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def register_and_login(client: TestClient, *, role: str, prefix: str) -> tuple[dict, dict[str, str]]:
    payload = {
        "email": f"{prefix}@example.com",
        "password": "testpassword123",
        "full_name": f"Test {role.title()}",
        "role": role,
    }
    registered = client.post("/api/v1/auth/register", json=payload)
    assert registered.status_code == 201, registered.text
    login = client.post(
        "/api/v1/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login.status_code == 200, login.text
    return registered.json(), {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.fixture
def student(client):
    return register_and_login(client, role="student", prefix="student")


@pytest.fixture
def admin(client):
    return register_and_login(client, role="admin", prefix="admin")


@pytest.fixture
def instructor(client):
    return register_and_login(client, role="instructor", prefix="instructor")


@pytest.fixture
def ta(client):
    return register_and_login(client, role="ta", prefix="ta")
