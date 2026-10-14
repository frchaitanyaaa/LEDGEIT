import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError


def test_user_keys_append_only(engine, seeded):
    with engine.begin() as c:
        uid = c.execute(text("SELECT id FROM users LIMIT 1")).scalar()
        c.execute(text("INSERT INTO user_keys(user_id, public_key) VALUES (:u, 'k')"), {"u": uid})
    for stmt in ["UPDATE user_keys SET public_key='x'", "DELETE FROM user_keys", "TRUNCATE user_keys CASCADE"]:
        with pytest.raises(DBAPIError, match="append-only"), engine.begin() as c:
            c.execute(text(stmt))


def test_model_identity_immutable(engine, seeded):
    with engine.begin() as c:
        c.execute(text("INSERT INTO ai_models(name, version, weights_sha256, framework, dataset_version) "
                       "VALUES ('m', '1', :h, 'f', 'd')"), {"h": "a" * 64})
        c.execute(text("UPDATE ai_models SET status='APPROVED' WHERE name='m'"))  # allowed
    with pytest.raises(DBAPIError, match="immutable"), engine.begin() as c:
        c.execute(text("UPDATE ai_models SET weights_sha256=:h WHERE name='m'"), {"h": "b" * 64})


def test_lines_have_genesis_heads(engine, seeded):
    from ledgeit_proof import genesis_hash

    with engine.begin() as c:
        rows = c.execute(text(
            "SELECT l.code, h.last_seq, h.last_event_hash FROM production_lines l JOIN line_heads h ON h.line_id=l.id"
        )).all()
    assert {r[0] for r in rows} == {"LINE-A", "LINE-B"}
    for code, seq, h in rows:
        assert seq == 0 and h == genesis_hash(code)
