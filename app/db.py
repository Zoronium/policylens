import uuid
from datetime import UTC, datetime
from functools import lru_cache

from sqlalchemy import JSON, DateTime, String, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


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
    owner_id: Mapped[str | None] = mapped_column(String(64), index=True)  # Clerk user id


@lru_cache
def _sessionmaker(url: str) -> sessionmaker[Session]:
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
    engine = create_engine(url, **kwargs)
    Base.metadata.create_all(engine)
    # create_all never alters an existing table: add the column older databases lack.
    if "owner_id" not in {c["name"] for c in inspect(engine).get_columns("policies")}:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE policies ADD COLUMN owner_id VARCHAR(64)"))
            conn.execute(text("CREATE INDEX ix_policies_owner_id ON policies (owner_id)"))
    return sessionmaker(engine, expire_on_commit=False)
