"""Files API 端到端测试。"""

from __future__ import annotations

from collections.abc import AsyncIterator
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
    tmp_path, test_engine: AsyncEngine
) -> AsyncIterator[AsyncClient]:
    """覆盖 ``get_db`` 到 in-memory，并把浏览根目录设为 ``tmp_path``。"""

    maker = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    allowed_roots = [str(tmp_path)]

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with maker() as session:
            await init_default_settings(session)
            result = await session.execute(
                select(Setting).where(Setting.key == "file.allowed_browse_roots").limit(1)
            )
            row = result.scalar_one_or_none()
            if row is not None:
                row.value = cast(Any, allowed_roots)
            else:
                session.add(Setting(key="file.allowed_browse_roots", value=allowed_roots))
            await session.commit()
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def test_browse_returns_entries(client: AsyncClient, tmp_path) -> None:
    """``POST /api/v1/files/browse`` 返回目录条目。"""

    root = tmp_path / "source"
    root.mkdir()
    (root / "Season 01").mkdir()
    (root / "ep01.mkv").write_bytes(b"video")

    response = await client.post("/api/v1/files/browse", json={"path": str(root)})

    assert response.status_code == 200
    body = response.json()
    assert body["current_path"] == str(root.resolve(strict=False))
    names = [entry["name"] for entry in body["entries"]]
    assert names == ["Season 01", "ep01.mkv"]


async def test_browse_outside_allowed_roots_returns_400(
    client: AsyncClient, tmp_path
) -> None:
    """browse 越界返回 400。"""

    outside = tmp_path.parent / "outside"
    outside.mkdir(exist_ok=True)

    response = await client.post("/api/v1/files/browse", json={"path": str(outside)})

    assert response.status_code == 400


async def test_validate_video_returns_200(client: AsyncClient, tmp_path) -> None:
    """合法视频通过校验。"""

    target = tmp_path / "episode.mp4"
    target.write_bytes(b"video")

    response = await client.post("/api/v1/files/validate", json={"path": str(target)})

    assert response.status_code == 200
    body = response.json()
    assert body["path"] == str(target.resolve(strict=False))
    assert body["is_video"] is True
    assert body["extension"] == ".mp4"


async def test_validate_non_video_returns_400(client: AsyncClient, tmp_path) -> None:
    """非视频返回 400。"""

    target = tmp_path / "notes.txt"
    target.write_text("hello", encoding="utf-8")

    response = await client.post("/api/v1/files/validate", json={"path": str(target)})

    assert response.status_code == 400
