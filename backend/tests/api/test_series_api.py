"""Series API 端到端测试。

覆盖：
- GET 空列表 / 列出已创建项 / 按 library_id 过滤；
- POST 无路径创建 (201)、路径落在 library 根目录内 (201)、路径越界 (400)、
  library_id 不存在 (400)；
- GET /{id} 详情 / 不存在 404；
- PUT 改名 (200) / 路径越界 (400)；
- DELETE 204 + 二次 GET 列表为空 / 不存在 ID 直接 404。

测试用 in-memory SQLite + ``ASGITransport``，fixture 与 T16 libraries 一致：
``file.allowed_browse_roots`` 覆写为 ``tmp_path``，再通过 ``POST /libraries``
构造一个真实 library 作为 series 的路径参照。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, cast

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
    tmp_path: Path, test_engine: AsyncEngine
) -> AsyncIterator[AsyncClient]:
    """覆盖 ``get_db`` 到 in-memory，并把 ``file.allowed_browse_roots`` 设为 ``tmp_path``。"""

    maker = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    allowed_roots = [str(tmp_path)]

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with maker() as session:
            await init_default_settings(session)
            result = await session.execute(
                select(Setting)
                .where(Setting.key == "file.allowed_browse_roots")
                .limit(1)
            )
            row = result.scalar_one_or_none()
            if row is not None:
                row.value = cast(Any, allowed_roots)
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


async def _create_library(
    client: AsyncClient, tmp_path: Path, name: str = "动画"
) -> dict[str, Any]:
    """辅助：通过 POST /libraries 建一个 library，断言成功并返回响应体。"""

    resp = await client.post(
        "/api/v1/libraries",
        json={
            "name": name,
            "staging_root": str(tmp_path / "staging"),
            "target_root": str(tmp_path / "target"),
        },
    )
    assert resp.status_code == 201
    return cast(dict[str, Any], resp.json())


async def test_get_series_returns_empty_list(client: AsyncClient) -> None:
    """``GET /api/v1/series`` 在没有任何 series 时返回空列表。"""

    response = await client.get("/api/v1/series")

    assert response.status_code == 200
    assert response.json() == []


async def test_post_series_creates_without_path(client: AsyncClient) -> None:
    """``POST /api/v1/series`` 仅传 name 时返回 201，其余字段走默认值。"""

    response = await client.post("/api/v1/series", json={"name": "三叉戟"})

    assert response.status_code == 201
    body = response.json()
    assert body["id"] >= 1
    assert body["name"] == "三叉戟"
    assert body["emby_series_id"] is None
    assert body["library_id"] is None
    assert body["library_name"] is None
    assert body["staging_path"] is None
    assert body["target_path"] is None
    assert body["default_season"] == 1
    assert body["enabled"] is True
    assert "created_at" in body and "updated_at" in body


async def test_post_series_creates_when_paths_inside_library(
    client: AsyncClient, tmp_path: Path
) -> None:
    """``POST`` 当 staging_path / target_path 落在 library 根目录内时返回 201。"""

    library = await _create_library(client, tmp_path)
    staging = tmp_path / "staging" / "series1"
    target = tmp_path / "target" / "series1"

    response = await client.post(
        "/api/v1/series",
        json={
            "name": "三叉戟",
            "library_id": library["id"],
            "staging_path": str(staging),
            "target_path": str(target),
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["library_id"] == library["id"]
    assert body["library_name"] == library["name"]
    assert body["staging_path"] == str(staging)
    assert body["target_path"] == str(target)


async def test_post_series_rejects_staging_path_outside_library(
    client: AsyncClient, tmp_path: Path
) -> None:
    """``POST`` 时 staging_path 落在 library.staging_root 之外返回 400。"""

    library = await _create_library(client, tmp_path)
    outside = tmp_path.parent / "outside-staging"

    response = await client.post(
        "/api/v1/series",
        json={
            "name": "三叉戟",
            "library_id": library["id"],
            "staging_path": str(outside),
            "target_path": str(tmp_path / "target" / "series1"),
        },
    )

    assert response.status_code == 400
    assert "staging_path" in response.text or "不在" in response.text


async def test_post_series_rejects_target_path_outside_library(
    client: AsyncClient, tmp_path: Path
) -> None:
    """``POST`` 时 target_path 落在 library.target_root 之外返回 400。"""

    library = await _create_library(client, tmp_path)
    outside = tmp_path.parent / "outside-target"

    response = await client.post(
        "/api/v1/series",
        json={
            "name": "三叉戟",
            "library_id": library["id"],
            "staging_path": str(tmp_path / "staging" / "series1"),
            "target_path": str(outside),
        },
    )

    assert response.status_code == 400
    assert "target_path" in response.text or "不在" in response.text


async def test_post_series_rejects_unknown_library_id(
    client: AsyncClient,
) -> None:
    """``POST`` 时 library_id 指向不存在的 library 返回 400。"""

    response = await client.post(
        "/api/v1/series",
        json={"name": "幽灵", "library_id": 9999},
    )

    assert response.status_code == 400
    assert "library" in response.text


async def test_get_series_lists_created(
    client: AsyncClient, tmp_path: Path
) -> None:
    """``POST`` 之后 ``GET /api/v1/series`` 能看到全部 series。"""

    library = await _create_library(client, tmp_path)
    await client.post(
        "/api/v1/series",
        json={"name": "A", "library_id": library["id"]},
    )
    await client.post("/api/v1/series", json={"name": "B"})

    response = await client.get("/api/v1/series")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    names = {item["name"] for item in body}
    assert names == {"A", "B"}


async def test_get_series_filter_by_library_id(
    client: AsyncClient, tmp_path: Path
) -> None:
    """``GET /api/v1/series?library_id=`` 只返回指定 library 下的 series。"""

    library = await _create_library(client, tmp_path)
    await client.post(
        "/api/v1/series",
        json={"name": "A", "library_id": library["id"]},
    )
    await client.post("/api/v1/series", json={"name": "B"})

    response = await client.get(f"/api/v1/series?library_id={library['id']}")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "A"
    assert body[0]["library_id"] == library["id"]


async def test_get_series_by_id_returns_detail(
    client: AsyncClient,
) -> None:
    """``GET /api/v1/series/{id}`` 返回单个 series 详情。"""

    create_resp = await client.post("/api/v1/series", json={"name": "三叉戟"})
    series_id = create_resp.json()["id"]

    response = await client.get(f"/api/v1/series/{series_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == series_id
    assert body["name"] == "三叉戟"


async def test_get_series_by_id_returns_404_when_not_found(
    client: AsyncClient,
) -> None:
    """``GET /api/v1/series/{id}`` 在 id 不存在时返回 404。"""

    response = await client.get("/api/v1/series/9999")

    assert response.status_code == 404


async def test_put_series_updates_name(
    client: AsyncClient,
) -> None:
    """``PUT /api/v1/series/{id}`` 改名返回 200，再次 GET 看到新名字。"""

    create_resp = await client.post("/api/v1/series", json={"name": "旧名字"})
    series_id = create_resp.json()["id"]

    put_resp = await client.put(
        f"/api/v1/series/{series_id}",
        json={"name": "新名字"},
    )

    assert put_resp.status_code == 200
    assert put_resp.json()["name"] == "新名字"

    get_resp = await client.get(f"/api/v1/series/{series_id}")
    assert get_resp.json()["name"] == "新名字"


async def test_put_series_rejects_path_outside_library(
    client: AsyncClient, tmp_path: Path
) -> None:
    """``PUT`` 时把 staging_path 改到 library 根目录之外返回 400。"""

    library = await _create_library(client, tmp_path)
    create_resp = await client.post(
        "/api/v1/series",
        json={
            "name": "三叉戟",
            "library_id": library["id"],
            "staging_path": str(tmp_path / "staging" / "s1"),
            "target_path": str(tmp_path / "target" / "s1"),
        },
    )
    series_id = create_resp.json()["id"]

    put_resp = await client.put(
        f"/api/v1/series/{series_id}",
        json={"staging_path": str(tmp_path.parent / "leaked")},
    )

    assert put_resp.status_code == 400


async def test_delete_series_removes_it(
    client: AsyncClient,
) -> None:
    """``DELETE /api/v1/series/{id}`` 返回 204，之后列表为空。"""

    create_resp = await client.post("/api/v1/series", json={"name": "三叉戟"})
    series_id = create_resp.json()["id"]

    del_resp = await client.delete(f"/api/v1/series/{series_id}")

    assert del_resp.status_code == 204

    list_resp = await client.get("/api/v1/series")
    assert list_resp.status_code == 200
    assert list_resp.json() == []


async def test_delete_series_returns_404_when_not_found(
    client: AsyncClient,
) -> None:
    """``DELETE /api/v1/series/{id}`` 在 id 不存在时返回 404。"""

    response = await client.delete("/api/v1/series/9999")

    assert response.status_code == 404
