"""Libraries API 端到端测试。

覆盖：
- GET 空列表 / 列出已创建项；
- POST 路径在 allowed_browse_roots 内允许 (201)，在外拒绝 (400)；
- GET /{id} 详情 / 不存在 404；
- PUT 改名 / 路径越界 400；
- DELETE 204 + 二次 GET 不存在 404 / 不存在 ID 直接 404。

测试用 in-memory SQLite + ``ASGITransport``，并通过 ``override_get_db``
把 ``file.allowed_browse_roots`` 覆写为 ``tmp_path``，保证路径校验生效于
临时目录之内。
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.api.deps import get_db
from app.db import Base
from app.db.models import Setting
from app.main import app
from app.services.settings import init_default_settings


@pytest.fixture
async def test_engine() -> AsyncIterator[AsyncEngine]:
    """提供内存 SQLite 异步引擎并建表。"""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
async def client(
    tmp_path, test_engine: AsyncEngine
) -> AsyncIterator[AsyncClient]:
    """覆盖 ``get_db`` 到 in-memory，并把 ``file.allowed_browse_roots`` 设为 ``tmp_path``。"""
    maker = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    allowed_roots = [str(tmp_path)]

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with maker() as session:
            await init_default_settings(session)
            # 把 allowed_browse_roots 重写为 tmp_path，让路径校验生效
            result = await session.execute(
                select(Setting).where(Setting.key == "file.allowed_browse_roots").limit(1)
            )
            row = result.scalar_one_or_none()
            if row is not None:
                row.value = allowed_roots
            else:
                session.add(
                    Setting(key="file.allowed_browse_roots", value=allowed_roots)
                )
            await session.commit()
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def test_get_libraries_returns_empty_list(client: AsyncClient) -> None:
    """``GET /api/v1/libraries`` 在没有任何 library 时返回空列表。"""
    response = await client.get("/api/v1/libraries")

    assert response.status_code == 200
    assert response.json() == []


async def test_post_library_creates_when_paths_inside_allowed_roots(
    client: AsyncClient, tmp_path
) -> None:
    """``POST /api/v1/libraries`` 当 ``staging_root`` / ``target_root`` 在允许根内时返回 201。"""
    staging = tmp_path / "staging"
    target = tmp_path / "target"
    payload = {
        "name": "动画",
        "collection_type": "tvshows",
        "staging_root": str(staging),
        "target_root": str(target),
    }

    response = await client.post("/api/v1/libraries", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["id"] >= 1
    assert body["name"] == "动画"
    assert body["collection_type"] == "tvshows"
    assert body["staging_root"] == str(staging)
    assert body["target_root"] == str(target)
    assert body["enabled"] is True
    assert body["emby_library_id"] is None
    assert "created_at" in body and "updated_at" in body


async def test_post_library_rejects_staging_root_outside_allowed_roots(
    client: AsyncClient, tmp_path
) -> None:
    """``POST`` 时 ``staging_root`` 落在允许根之外返回 400。"""
    outside = tmp_path.parent / "outside-staging"
    payload = {
        "name": "动画",
        "staging_root": str(outside),
        "target_root": str(tmp_path / "target"),
    }

    response = await client.post("/api/v1/libraries", json=payload)

    assert response.status_code == 400
    assert "staging_root" in response.text or "不在允许" in response.text


async def test_post_library_rejects_target_root_outside_allowed_roots(
    client: AsyncClient, tmp_path
) -> None:
    """``POST`` 时 ``target_root`` 落在允许根之外返回 400。"""
    outside = tmp_path.parent / "outside-target"
    payload = {
        "name": "动画",
        "staging_root": str(tmp_path / "staging"),
        "target_root": str(outside),
    }

    response = await client.post("/api/v1/libraries", json=payload)

    assert response.status_code == 400
    assert "target_root" in response.text or "不在允许" in response.text


async def test_get_libraries_lists_created(client: AsyncClient, tmp_path) -> None:
    """``POST`` 之后 ``GET /api/v1/libraries`` 能看到新建项。"""
    payload = {
        "name": "动画",
        "staging_root": str(tmp_path / "staging"),
        "target_root": str(tmp_path / "target"),
    }
    create_resp = await client.post("/api/v1/libraries", json=payload)
    assert create_resp.status_code == 201

    response = await client.get("/api/v1/libraries")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "动画"


async def test_get_library_by_id_returns_detail(
    client: AsyncClient, tmp_path
) -> None:
    """``GET /api/v1/libraries/{id}`` 返回单个 library 详情。"""
    create_resp = await client.post(
        "/api/v1/libraries",
        json={
            "name": "电视剧",
            "staging_root": str(tmp_path / "staging"),
            "target_root": str(tmp_path / "target"),
        },
    )
    library_id = create_resp.json()["id"]

    response = await client.get(f"/api/v1/libraries/{library_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == library_id
    assert body["name"] == "电视剧"


async def test_get_library_by_id_returns_404_when_not_found(
    client: AsyncClient,
) -> None:
    """``GET /api/v1/libraries/{id}`` 在 id 不存在时返回 404。"""
    response = await client.get("/api/v1/libraries/9999")

    assert response.status_code == 404


async def test_put_library_updates_name(client: AsyncClient, tmp_path) -> None:
    """``PUT /api/v1/libraries/{id}`` 改名返回 200，再次 GET 看到新名字。"""
    create_resp = await client.post(
        "/api/v1/libraries",
        json={
            "name": "旧名字",
            "staging_root": str(tmp_path / "staging"),
            "target_root": str(tmp_path / "target"),
        },
    )
    library_id = create_resp.json()["id"]

    put_resp = await client.put(
        f"/api/v1/libraries/{library_id}",
        json={"name": "新名字"},
    )

    assert put_resp.status_code == 200
    assert put_resp.json()["name"] == "新名字"

    get_resp = await client.get(f"/api/v1/libraries/{library_id}")
    assert get_resp.json()["name"] == "新名字"


async def test_put_library_rejects_path_outside_allowed_roots(
    client: AsyncClient, tmp_path
) -> None:
    """``PUT`` 时把 ``staging_root`` 改到允许根之外返回 400，原值不变。"""
    create_resp = await client.post(
        "/api/v1/libraries",
        json={
            "name": "动画",
            "staging_root": str(tmp_path / "staging"),
            "target_root": str(tmp_path / "target"),
        },
    )
    library_id = create_resp.json()["id"]
    original_staging = create_resp.json()["staging_root"]

    put_resp = await client.put(
        f"/api/v1/libraries/{library_id}",
        json={"staging_root": str(tmp_path.parent / "leaked")},
    )

    assert put_resp.status_code == 400

    get_resp = await client.get(f"/api/v1/libraries/{library_id}")
    assert get_resp.json()["staging_root"] == original_staging


async def test_delete_library_removes_it(client: AsyncClient, tmp_path) -> None:
    """``DELETE /api/v1/libraries/{id}`` 返回 204，之后 ``GET`` 列表为空。"""
    create_resp = await client.post(
        "/api/v1/libraries",
        json={
            "name": "动画",
            "staging_root": str(tmp_path / "staging"),
            "target_root": str(tmp_path / "target"),
        },
    )
    library_id = create_resp.json()["id"]

    del_resp = await client.delete(f"/api/v1/libraries/{library_id}")

    assert del_resp.status_code == 204

    list_resp = await client.get("/api/v1/libraries")
    assert list_resp.status_code == 200
    assert list_resp.json() == []


async def test_delete_library_returns_404_when_not_found(
    client: AsyncClient,
) -> None:
    """``DELETE /api/v1/libraries/{id}`` 在 id 不存在时返回 404。"""
    response = await client.delete("/api/v1/libraries/9999")

    assert response.status_code == 404
