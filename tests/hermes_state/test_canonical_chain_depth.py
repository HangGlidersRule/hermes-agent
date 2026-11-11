"""Regression: _canonical_chain must follow compression lineages deeper than 100 sessions.

A long-lived Slack channel's lineage reached 152 compressions. The old fixed 100-step bound
refused every /discard on it as ``admission_conflict``, so the chat stayed paused for good.
"""
import pytest

from hermes_state import SessionDB
from hermes_state_compression import _CHAIN_CAP
from hermes_state_runtime import RuntimeStoreError, _canonical_chain


def _lineage(tmp_path, depth):
    db = SessionDB(db_path=tmp_path / 'state.db')
    ids = [f's{i:04d}' for i in range(depth)]
    for i, sid in enumerate(ids):
        db.create_session(sid, source='test', parent_session_id=ids[i - 1] if i else None)
        if i < depth - 1:
            db.end_session(sid, 'compression')
    return db, ids


@pytest.mark.parametrize('depth', [2, 101, 152])
def test_canonical_chain_reaches_the_tip_of_a_deep_lineage(tmp_path, depth):
    db, ids = _lineage(tmp_path, depth)
    try:
        with db._read_ctx() as conn:
            assert _canonical_chain(conn, ids[0]) == ids
            assert db.get_compression_chain(ids[0]) == ids  # the two walkers agree
    finally:
        db.close()


def test_canonical_chain_still_refuses_beyond_the_shared_cap(tmp_path, monkeypatch):
    import hermes_state_compression
    monkeypatch.setattr(hermes_state_compression, '_CHAIN_CAP', 5)
    db, ids = _lineage(tmp_path, 8)
    try:
        with db._read_ctx() as conn, pytest.raises(RuntimeStoreError):
            _canonical_chain(conn, ids[0])
    finally:
        db.close()
    assert _CHAIN_CAP >= 1000
