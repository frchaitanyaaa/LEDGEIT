from ledgeit_proof import generate_keypair


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_login_me_and_bad_password(client, seeded, auth):
    r = client.post("/api/v1/auth/login", json={"email": "qe@ledgeit.dev", "password": "wrong"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"
    h = auth("qe")
    me = client.get("/api/v1/auth/me", headers=h).json()
    assert me["role"] == "QUALITY_ENGINEER" and me["employee_code"] == "QE-0042"
    assert me["public_key"] is None


def test_missing_token_and_refresh(client, seeded):
    assert client.get("/api/v1/auth/me").status_code == 401
    r = client.post("/api/v1/auth/login", json={"email": "qm@ledgeit.dev", "password": "ledgeit123"}).json()
    r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": r["refresh_token"]})
    assert r2.status_code == 200
    # an access token is not a refresh token
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": r["access_token"]}).status_code == 401


def test_register_keys_keeps_history(client, auth):
    h = auth("qe")
    k1, k2 = generate_keypair(), generate_keypair()
    assert client.post("/api/v1/auth/keys", headers=h, json={"public_key": k1.public_key_b64}).status_code == 201
    me = client.post("/api/v1/auth/keys", headers=h, json={"public_key": k2.public_key_b64}).json()
    assert [k["public_key"] for k in me["public_keys"]] == [k1.public_key_b64, k2.public_key_b64]
    assert me["public_key"] == k2.public_key_b64
    bad = client.post("/api/v1/auth/keys", headers=h, json={"public_key": "AAAA"})
    assert bad.status_code == 422


def test_rbac_users_admin_only(client, auth):
    body = {"employee_code": "QE-9", "full_name": "N", "email": "n@x.dev", "password": "password1",
            "role": "QUALITY_ENGINEER"}
    assert client.post("/api/v1/users", headers=auth("qe"), json=body).status_code == 403
    assert client.post("/api/v1/users", headers=auth("admin"), json=body).status_code == 201
    assert client.post("/api/v1/users", headers=auth("admin"), json=body).status_code == 409
    users = client.get("/api/v1/users", headers=auth("auditor")).json()
    assert any(u["employee_code"] == "QE-9" for u in users)


def test_public_endpoint_rate_limited(client):
    from ledgeit_api.core.ratelimit import public_limiter

    public_limiter.hits.clear()
    codes = [client.get("/api/v1/public/verify/NOPE").status_code for _ in range(32)]
    assert codes[:30] == [404] * 30 and codes[-1] == 429
    public_limiter.hits.clear()
