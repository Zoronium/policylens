import uuid
from datetime import UTC, datetime
from functools import lru_cache

from sqlalchemy import JSON, DateTime, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


class Policy(Base):
    __tablename__ = "policies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    source_name: Mapped[str | None] = mapped_column(String(255))
    model: Mapped[str] = mapped_column(String(100))
    pages: Mapped[list] = mapped_column(JSON)
    coverage: Mapped[dict] = mapped_column(JSON)


@lru_cache
def _sessionmaker(url: str) -> sessionmaker[Session]:
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
    engine = create_engine(url, **kwargs)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


def get_session():
    with _sessionmaker(get_settings().database_url)() as session:
        yield session
