import uuid

import pytest

from tests.conftest import API, BAG, auth, create_bag, register


async def test_create_baggage_defaults_and_server_fields(client):
    t = await register(client)
    bag = await create_bag(client, t)
    assert bag["user_id"] == t["user"]["id"]
    assert bag["token_id"].startswith("bag_") and len(bag["token_id"]) > 20
    assert bag["category"] == "luggage" and bag["status"] == "active"  # status defaulted
    assert bag["created_at"].endswith("Z") and bag["updated_at"].endswith("Z")
    uuid.UUID(bag["id"])


async def test_category_defaults_to_general_and_brand_is_optional(client):
    t = await register(client)
    r = await client.post(f"{API}/baggage", headers=auth(t), json={"name": "Case", "color": "red"})
    assert r.status_code == 201
    assert r.json()["category"] == "general" and r.json()["brand"] is None


async def test_token_ids_are_unique(client):
    t = await register(client)
    ids = {(await create_bag(client, t))["token_id"] for _ in range(5)}
    assert len(ids) == 5


@pytest.mark.parametrize(
    "patch",
    [
        {"category": "spaceship"},  # not in the enum
        {"status": "stolen"},
        {"category": 1},  # old integer-id style is no longer accepted
        {"name": ""},
        {"color": ""},
        {"user_id": str(uuid.uuid4())},  # ownership can't be client-supplied
        {"token_id": "mine"},
        {"id": str(uuid.uuid4())},
        {"created_at": "2020-01-01T00:00:00Z"},
    ],
)
async def test_create_validation_400(client, patch):
    t = await register(client)
    r = await client.post(f"{API}/baggage", headers=auth(t), json={**BAG, **patch})
    assert r.status_code == 400, patch
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_remarks_optional_and_nullable(client):
    t = await register(client)
    body = {k: v for k, v in BAG.items() if k != "remarks"}
    r = await client.post(f"{API}/baggage", headers=auth(t), json=body)
    assert r.status_code == 201 and r.json()["remarks"] is None


async def test_list_is_scoped_paginated_and_filterable(client):
    a = await register(client)
    b = await register(client, email="b@gmail.com")
    for i in range(3):
        await create_bag(client, a, name=f"A{i}")
    await create_bag(client, a, name="Cam", category="camera", status="lost")
    await create_bag(client, b, name="B0")

    r = await client.get(f"{API}/baggage?limit=2&page=1", headers=auth(a))
    body = r.json()
    assert body["total"] == 4 and len(body["items"]) == 2 and body["page"] == 1
    r2 = await client.get(f"{API}/baggage?limit=2&page=2", headers=auth(a))
    names1 = {i["name"] for i in body["items"]}
    names2 = {i["name"] for i in r2.json()["items"]}
    assert len(names2) == 2 and names1.isdisjoint(names2)

    assert (await client.get(f"{API}/baggage?category=camera", headers=auth(a))).json()[
        "total"
    ] == 1
    assert (await client.get(f"{API}/baggage?status=active", headers=auth(a))).json()["total"] == 3
    assert (await client.get(f"{API}/baggage", headers=auth(b))).json()["total"] == 1

    for bad in ("limit=1000", "page=0", "status=nope", "category=nope"):
        assert (await client.get(f"{API}/baggage?{bad}", headers=auth(a))).status_code == 400, bad


async def test_ownership_enforced_with_404(client):
    a = await register(client)
    b = await register(client, email="b@gmail.com")
    bag = await create_bag(client, a)
    url = f"{API}/baggage/{bag['id']}"
    assert (await client.get(url, headers=auth(a))).status_code == 200
    assert (await client.get(url, headers=auth(b))).status_code == 404
    assert (await client.patch(url, headers=auth(b), json={"name": "x"})).status_code == 404
    assert (
        await client.patch(f"{url}/status", headers=auth(b), json={"status": "lost"})
    ).status_code == 404
    assert (await client.delete(url, headers=auth(b))).status_code == 404
    still = (await client.get(url, headers=auth(a))).json()
    assert still["name"] == "My Laptop Bag" and still["status"] == "active"


async def test_patch_updates_only_sent_fields(client):
    t = await register(client)
    bag = await create_bag(client, t)
    r = await client.patch(
        f"{API}/baggage/{bag['id']}",
        headers=auth(t),
        json={"name": "Work Laptop Bag", "category": "cargo", "status": "lost", "remarks": None},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Work Laptop Bag"
    assert body["category"] == "cargo" and body["status"] == "lost"
    assert body["remarks"] is None
    assert body["brand"] == "BrandName" and body["color"] == "#000000"
    assert body["token_id"] == bag["token_id"] and body["user_id"] == bag["user_id"]
    assert body["updated_at"] > bag["updated_at"]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": None},
        {"category": None},
        {"status": None},
        {"category": "spaceship"},
        {"user_id": str(uuid.uuid4())},
        {"token_id": "x"},
        {"id": str(uuid.uuid4())},
        {"updated_at": "2020-01-01T00:00:00Z"},
    ],
)
async def test_patch_validation_400(client, payload):
    t = await register(client)
    bag = await create_bag(client, t)
    r = await client.patch(f"{API}/baggage/{bag['id']}", headers=auth(t), json=payload)
    assert r.status_code == 400, payload


async def test_status_change_route(client):
    t = await register(client)
    bag = await create_bag(client, t)
    url = f"{API}/baggage/{bag['id']}/status"
    r = await client.patch(url, headers=auth(t), json={"status": "recovered"})
    assert r.status_code == 200 and r.json()["status"] == "recovered"
    assert r.json()["name"] == bag["name"]
    bad = await client.patch(url, headers=auth(t), json={"status": "stolen"})
    assert bad.status_code == 400


async def test_delete_baggage(client):
    t = await register(client)
    bag = await create_bag(client, t)
    url = f"{API}/baggage/{bag['id']}"
    r = await client.delete(url, headers=auth(t))
    assert r.status_code == 204 and r.content == b""
    assert (await client.get(url, headers=auth(t))).status_code == 404
    assert (await client.delete(url, headers=auth(t))).status_code == 404
    assert (await client.get(f"{API}/baggage/{uuid.uuid4()}", headers=auth(t))).status_code == 404
