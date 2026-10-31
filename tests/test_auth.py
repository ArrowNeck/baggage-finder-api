import pytest
from sqlalchemy import select

from app.database.base import AsyncSessionLocal
from app.models import RefreshToken, User
from tests.conftest import API, SIGNUP, auth, register


async def test_sign_up_returns_user_and_tokens_without_password(client):
    data = await register(client)
    assert data["user"]["email"] == "john@gmail.com"  # normalised
    assert data["accessToken"] and data["refreshToken"]
    assert "password" not in data["user"] and "hashed_password" not in data["user"]
    assert "hashed_password" not in str(data)


async def test_password_is_stored_as_bcrypt_hash(client):
    await register(client)
    async with AsyncSessionLocal() as s:
        user = (await s.execute(select(User))).scalar_one()
    assert user.hashed_password.startswith("$2")
    assert SIGNUP["password"] not in user.hashed_password


async def test_duplicate_email_conflict_is_case_insensitive(client):
    await register(client)
    r = await client.post(f"{API}/signUp", json={**SIGNUP, "email": "JOHN@gmail.COM"})
    assert r.status_code == 409
    assert r.json() == {
        "success": False,
        "error": {
            "code": "EMAIL_EXISTS",
            "message": "An account with this email already exists",
            "details": [],
        },
    }


@pytest.mark.parametrize(
    "patch",
    [
        {"email": "not-an-email"},
        {"password": "short"},
        {"password": "é" * 40},  # 80 bytes: bcrypt would silently truncate / reject
        {"name": "  "},
        {"phone": "abc"},
        {"id": "5"},  # unknown fields are rejected
        {"is_admin": True},
    ],
)
async def test_sign_up_validation_400_and_never_echoes_password(client, patch):
    r = await client.post(f"{API}/signUp", json={**SIGNUP, **patch})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert r.json()["success"] is False
    assert SIGNUP["password"] not in r.text
    if "password" in patch:
        assert patch["password"] not in r.text


@pytest.mark.parametrize("field", ["passwordHash", "password"])
async def test_login_accepts_legacy_and_new_password_field(client, field):
    await register(client)
    r = await client.post(
        f"{API}/user/login", json={"email": "john@gmail.com", field: SIGNUP["password"]}
    )
    assert r.status_code == 200
    assert r.json()["user"]["name"] == "John Doe"
    assert {"user", "accessToken", "refreshToken"} <= r.json().keys()


async def test_login_failures_are_indistinguishable(client):
    await register(client)
    bad_pw = await client.post(
        f"{API}/user/login", json={"email": "john@gmail.com", "password": "nope-nope"}
    )
    bad_email = await client.post(
        f"{API}/user/login", json={"email": "x@gmail.com", "password": "nope-nope"}
    )
    assert bad_pw.status_code == bad_email.status_code == 401
    assert bad_pw.json() == bad_email.json()


async def test_overlong_login_password_is_401_not_500(client):
    await register(client)
    r = await client.post(
        f"{API}/user/login", json={"email": "john@gmail.com", "password": "é" * 60}
    )
    assert r.status_code == 401


async def test_protected_routes_need_a_valid_access_token(client):
    r = await client.get(f"{API}/baggage")
    assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"
    r = await client.get(f"{API}/baggage", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401
    tokens = await register(client)
    # a refresh token is not an access token
    r = await client.get(
        f"{API}/baggage", headers={"Authorization": f"Bearer {tokens['refreshToken']}"}
    )
    assert r.status_code == 401


async def test_expired_access_token_is_rejected(client, monkeypatch):
    from app.core import security
    from app.core.config import settings

    monkeypatch.setattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", -1)
    tokens = await register(client)
    assert security.decode_access_token(tokens["accessToken"]) is None
    assert (await client.get(f"{API}/baggage", headers=auth(tokens))).status_code == 401


async def test_refresh_rotates_and_reuse_revokes_everything(client):
    tokens = await register(client)
    r = await client.post(f"{API}/user/refresh", json={"refreshToken": tokens["refreshToken"]})
    assert r.status_code == 200
    new = r.json()
    assert new["refreshToken"] != tokens["refreshToken"]
    assert (await client.get(f"{API}/baggage", headers=auth(new))).status_code == 200

    # replaying the old token fails and burns the new one too
    r = await client.post(f"{API}/user/refresh", json={"refreshToken": tokens["refreshToken"]})
    assert r.status_code == 401
    r = await client.post(f"{API}/user/refresh", json={"refreshToken": new["refreshToken"]})
    assert r.status_code == 401


async def test_expired_refresh_token_is_rejected(client):
    from datetime import timedelta

    from app.utils.helpers import utcnow

    tokens = await register(client)
    async with AsyncSessionLocal() as s:
        row = (await s.execute(select(RefreshToken))).scalar_one()
        row.expires_at = utcnow() - timedelta(seconds=1)
        await s.commit()
    r = await client.post(f"{API}/user/refresh", json={"refreshToken": tokens["refreshToken"]})
    assert r.status_code == 401


async def test_refresh_tokens_are_stored_hashed_and_unknown_ones_rejected(client):
    tokens = await register(client)
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(RefreshToken))).scalars().all()
    assert rows and all(tokens["refreshToken"] not in r.token_hash for r in rows)
    r = await client.post(f"{API}/user/refresh", json={"refreshToken": "unknown"})
    assert r.status_code == 401


async def test_logout_revokes_refresh_token(client):
    tokens = await register(client)
    r = await client.post(f"{API}/user/logout", headers=auth(tokens))
    assert r.status_code == 204 and r.content == b""
    r = await client.post(f"{API}/user/refresh", json={"refreshToken": tokens["refreshToken"]})
    assert r.status_code == 401


async def test_logout_with_token_only_revokes_that_session(client):
    first = await register(client)
    second = (
        await client.post(
            f"{API}/user/login", json={"email": "john@gmail.com", "password": SIGNUP["password"]}
        )
    ).json()
    r = await client.post(
        f"{API}/user/logout", headers=auth(first), json={"refreshToken": first["refreshToken"]}
    )
    assert r.status_code == 204
    assert (
        await client.post(f"{API}/user/refresh", json={"refreshToken": first["refreshToken"]})
    ).status_code == 401
    assert (
        await client.post(f"{API}/user/refresh", json={"refreshToken": second["refreshToken"]})
    ).status_code == 200


async def test_change_password(client):
    tokens = await register(client)
    url = f"{API}/user/password"
    bad = await client.patch(
        url,
        headers=auth(tokens),
        json={"currentPassword": "wrong-wrong", "newPassword": "brand-new-password"},
    )
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "INVALID_CURRENT_PASSWORD"

    ok = await client.patch(
        url,
        headers=auth(tokens),
        json={"currentPassword": SIGNUP["password"], "newPassword": "brand-new-password"},
    )
    assert ok.status_code == 204
    login = f"{API}/user/login"
    refresh = await client.post(
        f"{API}/user/refresh", json={"refreshToken": tokens["refreshToken"]}
    )
    assert refresh.status_code == 401  # sessions revoked
    old = await client.post(login, json={"email": "john@gmail.com", "password": SIGNUP["password"]})
    assert old.status_code == 401
    new = await client.post(
        login, json={"email": "john@gmail.com", "password": "brand-new-password"}
    )
    assert new.status_code == 200


async def test_password_reset_flow(client, monkeypatch):
    sent = {}

    async def fake_deliver(email, token):
        sent["email"], sent["token"] = email, token

    monkeypatch.setattr("app.api.v1.endpoints.auth.deliver_reset_token", fake_deliver)
    tokens = await register(client)

    req = f"{API}/user/password/reset-request"
    unknown = await client.post(req, json={"email": "nobody@gmail.com"})
    assert "token" not in sent  # nothing delivered for an unknown account
    known = await client.post(req, json={"email": "john@gmail.com"})
    assert unknown.status_code == known.status_code == 202
    assert unknown.json() == known.json()
    assert sent["email"] == "john@gmail.com"

    reset = f"{API}/user/password/reset"
    bad = await client.post(reset, json={"resetToken": "bogus", "newPassword": "another-password"})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "INVALID_RESET_TOKEN"

    first_token = sent["token"]
    await client.post(req, json={"email": "john@gmail.com"})  # newer token supersedes the first
    stale = await client.post(
        reset, json={"resetToken": first_token, "newPassword": "another-password"}
    )
    assert stale.status_code == 400

    ok = await client.post(
        reset, json={"resetToken": sent["token"], "newPassword": "another-password"}
    )
    assert ok.status_code == 204
    again = await client.post(
        reset, json={"resetToken": sent["token"], "newPassword": "yet-another-pass"}
    )
    assert again.status_code == 400  # single use
    refresh = await client.post(
        f"{API}/user/refresh", json={"refreshToken": tokens["refreshToken"]}
    )
    assert refresh.status_code == 401
    login = await client.post(
        f"{API}/user/login", json={"email": "john@gmail.com", "password": "another-password"}
    )
    assert login.status_code == 200


async def test_expired_reset_token_is_rejected(client, monkeypatch):
    from datetime import timedelta

    from app.models import PasswordResetToken
    from app.utils.helpers import utcnow

    sent = {}

    async def fake_deliver(email, token):
        sent["token"] = token

    monkeypatch.setattr("app.api.v1.endpoints.auth.deliver_reset_token", fake_deliver)
    await register(client)
    await client.post(f"{API}/user/password/reset-request", json={"email": "john@gmail.com"})
    async with AsyncSessionLocal() as s:
        row = (await s.execute(select(PasswordResetToken))).scalar_one()
        row.expires_at = utcnow() - timedelta(seconds=1)
        await s.commit()
    r = await client.post(
        f"{API}/user/password/reset",
        json={"resetToken": sent["token"], "newPassword": "another-password"},
    )
    assert r.status_code == 400


async def test_rate_limit_on_login(client, monkeypatch):
    from app.core.config import settings
    from app.core.rate_limit import RateLimit

    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 3)
    RateLimit.reset()
    codes = [
        (
            await client.post(
                f"{API}/user/login", json={"email": "a@b.co", "password": "whatever1"}
            )
        ).status_code
        for _ in range(5)
    ]
    assert codes == [401, 401, 401, 429, 429]


async def test_request_id_health_and_error_shape(client):
    r = await client.get("/health", headers={"X-Request-ID": "abc12345"})
    assert r.status_code == 200 and r.headers["X-Request-ID"] == "abc12345"
    r = await client.get("/health", headers={"X-Request-ID": "bad id\nwith newline"})
    assert r.headers["X-Request-ID"] != "bad id\nwith newline"
    assert (await client.get("/ready")).status_code == 200
    r = await client.get(f"{API}/does-not-exist")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"
