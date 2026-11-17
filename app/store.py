"""Where policies live: MongoDB when MONGODB_URI is set, else SQL (SQLite by default).

Both stores speak the same three calls, so main.py never knows which one it has.
"""

import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from functools import lru_cache

from pymongo import DESCENDING, MongoClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import Policy, _sessionmaker


@dataclass
class PolicyRecord:
    source_name: str | None
    model: str
    pages: list
    coverage: dict
    owner_id: str | None = None  # Clerk user id; None = made while signed out
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class SqlStore:
    def __init__(self, session: Session):
        self.s = session

    def add(self, rec: PolicyRecord) -> None:
        self.s.add(Policy(**asdict(rec)))
        self.s.commit()

    def get(self, id: str) -> PolicyRecord | None:
        row = self.s.get(Policy, id)
        return _rec(row) if row else None

    def by_owner(self, owner_id: str) -> list[PolicyRecord]:
        q = select(Policy).where(Policy.owner_id == owner_id).order_by(Policy.created_at.desc())
        return [_rec(r) for r in self.s.scalars(q)]


def _rec(row: Policy) -> PolicyRecord:
    return PolicyRecord(
        id=row.id,
        created_at=row.created_at,
        source_name=row.source_name,
        model=row.model,
        pages=row.pages,
        coverage=row.coverage,
        owner_id=row.owner_id,
    )


class MongoStore:
    def __init__(self, coll):
        self.c = coll

    def add(self, rec: PolicyRecord) -> None:
        d = asdict(rec)
        d["_id"] = d.pop("id")
        self.c.insert_one(d)

    def get(self, id: str) -> PolicyRecord | None:
        d = self.c.find_one({"_id": id})
        return _from_doc(d) if d else None

    def by_owner(self, owner_id: str) -> list[PolicyRecord]:
        return [
            _from_doc(d)
            for d in self.c.find({"owner_id": owner_id}).sort("created_at", DESCENDING)
        ]


def _from_doc(d: dict) -> PolicyRecord:
    d = dict(d)
    return PolicyRecord(id=d.pop("_id"), **d)


@lru_cache
def _mongo_collection(uri: str, db: str):
    coll = MongoClient(uri, tz_aware=True, serverSelectionTimeoutMS=8000)[db]["policies"]
    coll.create_index([("owner_id", 1), ("created_at", -1)])
    return coll


def get_store():
    s = get_settings()
    if s.mongodb_uri:
        yield MongoStore(_mongo_collection(s.mongodb_uri, s.mongodb_db))
        return
    with _sessionmaker(s.database_url)() as session:
        yield SqlStore(session)
