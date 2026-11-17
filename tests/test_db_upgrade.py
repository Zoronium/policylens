import sqlite3

from app.db import _sessionmaker
from app.store import PolicyRecord, SqlStore


def test_database_made_before_owner_id_is_upgraded(tmp_path):
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE policies (id VARCHAR(36) PRIMARY KEY, created_at DATETIME, "
        "source_name VARCHAR(255), model VARCHAR(100), pages JSON, coverage JSON)"
    )
    con.commit()
    con.close()

    with _sessionmaker(f"sqlite:///{path}")() as session:
        store = SqlStore(session)
        rec = PolicyRecord(None, "m", ["p"], {}, owner_id="user_a")
        store.add(rec)
        assert store.get(rec.id).owner_id == "user_a"
        assert [p.id for p in store.by_owner("user_a")] == [rec.id]
