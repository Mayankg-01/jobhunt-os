import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from jobhunt.core.models import Base
from jobhunt.storage.database import get_engine, get_session_factory


@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def test_session(test_engine):
    Session = sessionmaker(bind=test_engine, expire_on_commit=False)
    session = Session()
    yield session
    session.rollback()
    session.close()