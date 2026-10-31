import uuid

from sqlalchemy import select

from app.database.base import AsyncSessionLocal
from app.models import Baggage, User
from tests.conftest import API, SIGNUP, auth, create_bag, register


async def test_get_own_user_only(client):
    a = await register(client)
    b = await register(client, email="b@gmail.com")
    own = await client.get(f"{API}/users/{a['user']['id']}", headers=auth(a))
    assert own.status_code == 200 and own.json()["email"] == "john@gmail.com"
    assert (await client.get(f"{API}/users/{b['user']['id']}", headers=auth(a))).status_code == 404
    assert (await client.get(f"{API}/users/{uuid.uuid4()}", headers=auth(a))).status_code == 404
    assert (await client.get(f"{API}/users/not-a-uuid", headers=auth(a))).status_code == 400


async def test_patch_user_profile_and_fcm_token(client):
    a = await register(client)
    url = f"{API}/users/{a['user']['id']}"
    r = await client.patch(
        url, headers=auth(a), json={"phone": "555-0100", "fcm_token": "new_fcm_token"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["phone"] == "555-0100" and body["fcm_token"] == "new_fcm_token"
    assert body["updated_at"] > body["created_at"]
    assert body["name"] == "John Doe"  # untouched fields stay

    cleared = await client.patch(url, headers=auth(a), json={"fcm_token": None})
    assert cleared.status_code == 200 and cleared.json()["fcm_token"] is None


async def test_patch_user_rejects_immutable_null_and_empty(client):
    a = await register(client)
    url = f"{API}/users/{a['user']['id']}"
    for payload in (
        {"id": str(uuid.uuid4())},
        {"created_at": "2020-01-01T00:00:00Z"},
        {"password": "x" * 10},
        {"hashed_password": "x"},
        {"name": None},
        {"email": None},
        {},
    ):
        r = await client.patch(url, headers=auth(a), json=payload)
        assert r.status_code == 400, payload


async def test_patch_user_email_conflict_and_normalisation(client):
    a = await register(client)
    await register(client, email="b@gmail.com")
    url = f"{API}/users/{a['user']['id']}"
    assert (
        await client.patch(url, headers=auth(a), json={"email": "B@gmail.com"})
    ).status_code == 409
    ok = await client.patch(url, headers=auth(a), json={"email": "New@Gmail.com"})
    assert ok.status_code == 200 and ok.json()["email"] == "new@gmail.com"
    same = await client.patch(url, headers=auth(a), json={"email": "new@gmail.com"})
    assert same.status_code == 200  # re-sending your own email is fine


async def test_cannot_patch_or_delete_other_user(client):
    a = await register(client)
    b = await register(client, email="b@gmail.com")
    other = f"{API}/users/{b['user']['id']}"
    assert (await client.patch(other, headers=auth(a), json={"name": "X"})).status_code == 404
    assert (await client.delete(other, headers=auth(a))).status_code == 404
    async with AsyncSessionLocal() as s:
        victim = (await s.execute(select(User).where(User.email == "b@gmail.com"))).scalar_one()
    assert victim.name == "John Doe" and victim.is_deleted is False


async def test_delete_user_disables_account_and_keeps_baggage(client):
    a = await register(client)
    await create_bag(client, a)

    r = await client.delete(f"{API}/users/{a['user']['id']}", headers=auth(a))
    assert r.status_code == 204
    # access token dies immediately; refresh and login are refused
    assert (await client.get(f"{API}/baggage", headers=auth(a))).status_code == 401
    refresh = await client.post(f"{API}/user/refresh", json={"refreshToken": a["refreshToken"]})
    assert refresh.status_code == 401
    login = await client.post(
        f"{API}/user/login", json={"email": "john@gmail.com", "password": SIGNUP["password"]}
    )
    assert login.status_code == 401
    # the email stays reserved and baggage rows are retained
    dup = await client.post(f"{API}/signUp", json=SIGNUP)
    assert dup.status_code == 409
    async with AsyncSessionLocal() as s:
        assert len((await s.execute(select(Baggage))).scalars().all()) == 1
