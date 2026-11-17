"""Live MongoDB round trip. Off by default (it needs the network and your Atlas URI):

    PL_TEST_MONGO=1 pytest tests/test_mongo_store.py
"""

import os

import pytest

from app.store import MongoStore, PolicyRecord, _mongo_collection

URI = os.environ.get("MONGODB_URI")  # read before the conftest fixture unsets it
pytestmark = pytest.mark.skipif(not os.environ.get("PL_TEST_MONGO"), reason="set PL_TEST_MONGO=1")


def test_round_trip_and_owner_listing(monkeypatch):
    coll = _mongo_collection(URI, "policylens_test")
    coll.delete_many({})
    store = MongoStore(coll)
    mine = PolicyRecord("a.txt", "m", ["p1"], {"sum_insured": {"value": "5"}}, owner_id="user_a")
    other = PolicyRecord(None, "m", ["p1"], {}, owner_id="user_b")
    store.add(mine)
    store.add(other)
    got = store.get(mine.id)
    assert (got.id, got.coverage, got.owner_id) == (mine.id, mine.coverage, "user_a")
    assert got.created_at.tzinfo is not None
    assert [p.id for p in store.by_owner("user_a")] == [mine.id]
    assert store.get("missing") is None
    coll.drop()
