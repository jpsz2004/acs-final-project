from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from app.infrastructure.models import Base


def create_engine_from_url(database_url: str):
    return create_engine(database_url, future=True, pool_pre_ping=True)


def create_session_factory(engine):
    return scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True))


def init_db(engine) -> None:
    Base.metadata.create_all(bind=engine)
