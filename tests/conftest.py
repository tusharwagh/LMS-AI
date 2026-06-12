import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session, sessionmaker

from lms.api.app import create_app
from lms.config import get_settings
from lms.shared.application.seed_api_users import DEFAULT_DEV_PASSWORD, ensure_default_api_users
from lms.shared.auth.jwt import create_access_token
from lms.shared.auth.roles import Role
from lms.shared.db.session import SessionLocal, engine


class AuthenticatedTestClient(TestClient):
    """TestClient that sends a Bearer JWT on every request unless overridden."""

    def __init__(self, *args, default_headers: dict[str, str] | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._default_headers = default_headers or {}

    def request(self, method: str, url, **kwargs):  # type: ignore[no-untyped-def]
        extra = kwargs.pop("headers", None) or {}
        headers = {**self._default_headers, **extra}
        return super().request(method, url, headers=headers, **kwargs)


@pytest.fixture(autouse=True)
def _settings_cache_clear(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_DEBUG", "false")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    get_settings.cache_clear()


def _test_needs_db_seed(request: pytest.FixtureRequest) -> bool:
    if request.node.get_closest_marker("unit"):
        return False
    # Smoke tests that only hit stateless HTTP endpoints.
    if request.node.name in {
        "test_health_and_docs",
        "test_health",
        "test_correlation_id_echoed",
        "test_auth_required_without_token",
    }:
        return False
    return True


@pytest.fixture(autouse=True)
def _seed_api_users(request: pytest.FixtureRequest) -> None:
    if not _test_needs_db_seed(request):
        return
    session = SessionLocal()
    try:
        ensure_default_api_users(session)
        session.commit()
    finally:
        session.close()


@pytest.fixture
def auth_headers() -> dict[str, str]:
    token = create_access_token("00000000-0001-4001-8001-000000000002", Role.LIBRARIAN)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers() -> dict[str, str]:
    token = create_access_token("00000000-0001-4001-8001-000000000001", Role.ADMIN)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(auth_headers: dict[str, str]) -> AuthenticatedTestClient:
    return AuthenticatedTestClient(create_app(), default_headers=auth_headers)


@pytest.fixture
def bare_client() -> TestClient:
    """Unauthenticated client for auth-negative tests."""
    return TestClient(create_app())


@pytest.fixture
def db_session() -> Session:
    """Integration session with outer rollback — each test leaves DB unchanged."""
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection, autoflush=False, expire_on_commit=False)()

    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess: Session, trans) -> None:  # type: ignore[no-untyped-def]
        if trans.nested and trans._parent is not None and not trans._parent.nested:
            sess.expire_all()
            sess.begin_nested()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def db_session_committed() -> Session:
    """Session that commits — for tests that need cross-request persistence."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def dev_password() -> str:
    return DEFAULT_DEV_PASSWORD
