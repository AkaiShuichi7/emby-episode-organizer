"""Settings API 端到端测试。

覆盖：GET 默认值、PUT 写库回读、API Key mask、复杂 value、/health 扩展、DB 不可达兜底。
"""

# pyright: reportMissingSuperCall=false

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.api.deps import get_db, get_settings_service
from app.db import Base
from app.main import app
from app.services.settings import SettingsService, init_default_settings


@pytest.fixture
async def test_engine() -> AsyncIterator[AsyncEngine]:
    """提供内存 SQLite 异步引擎并建表。"""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
async def client(test_engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    """覆盖 get_db 依赖到 in-memory，注入默认设置，包装 ASGI client。"""
    maker = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with maker() as session:
            await init_default_settings(session)
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def test_get_settings_returns_defaults(client: AsyncClient) -> None:
    """GET /api/v1/settings 返回默认 keys（init_default_settings 已跑）。"""
    response = await client.get("/api/v1/settings")

    assert response.status_code == 200
    body = response.json()
    assert body["file.source_mode"] == "copy"
    assert body["emby.auto_refresh"] is False
    assert body["file.allowed_browse_roots"] == ["/data"]


async def test_put_settings_persists_value(client: AsyncClient) -> None:
    """PUT /api/v1/settings 写入新值，GET 能读到。"""
    put_resp = await client.put(
        "/api/v1/settings", json={"emby.server_url": "http://x"}
    )
    assert put_resp.status_code == 200

    get_resp = await client.get("/api/v1/settings")
    assert get_resp.status_code == 200
    assert get_resp.json()["emby.server_url"] == "http://x"


async def test_get_settings_masks_api_key(client: AsyncClient) -> None:
    """GET 时 emby.api_key 字段被 mask 为 xxxx****last4。"""
    put_resp = await client.put(
        "/api/v1/settings",
        json={
            "emby.server_url": "http://x",
            "emby.api_key": "abcdef123456",
            "emby.auto_refresh": True,
        },
    )
    assert put_resp.status_code == 200

    response = await client.get("/api/v1/settings")
    body = response.json()

    assert body["emby.api_key"] == "xxxx****3456"


async def test_get_settings_without_api_key_does_not_error(
    client: AsyncClient,
) -> None:
    """GET 时 emby.api_key 未配置也不报错。"""
    response = await client.get("/api/v1/settings")
    assert response.status_code == 200
    # api_key 缺省时，响应里可不存在该字段，也可为 None/空 mask
    body = response.json()
    assert "emby.api_key" not in body or body.get("emby.api_key") in (None, "", "****")


async def test_put_settings_accepts_complex_value(client: AsyncClient) -> None:
    """PUT 接受 dict / list 等复杂 value。"""
    payload = {
        "file.allowed_browse_roots": ["/data", "/mnt/media"],
        "custom_dict": {"nested": "value"},
    }
    resp = await client.put("/api/v1/settings", json=payload)
    assert resp.status_code == 200

    get_resp = await client.get("/api/v1/settings")
    body = get_resp.json()
    assert body["file.allowed_browse_roots"] == ["/data", "/mnt/media"]
    assert body["custom_dict"] == {"nested": "value"}


async def test_health_returns_status_ok_with_emby_unconfigured(
    client: AsyncClient,
) -> None:
    """默认 /health 返回 status=ok + emby_configured=false。"""
    response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["emby_configured"] is False
    assert body["db_ok"] is True


async def test_health_emby_configured_true_after_setup(client: AsyncClient) -> None:
    """配置齐 Emby 三件套后 /health emby_configured=true。"""
    put_resp = await client.put(
        "/api/v1/settings",
        json={
            "emby.server_url": "http://x",
            "emby.api_key": "abc",
            "emby.auto_refresh": True,
        },
    )
    assert put_resp.status_code == 200

    response = await client.get("/health")
    assert response.json()["emby_configured"] is True


async def test_health_falls_back_when_settings_db_unavailable() -> None:
    """settings DB 不可达时 /health 仍 200，db_ok=false。"""

    class _BrokenService(SettingsService):
        """构造时不拿 session，``get_emby_config`` 直接抛错模拟 DB 故障。"""

        def __init__(self) -> None:  # noqa: D401 - test stub
            # 故意不调 super()，避免触发 session 初始化
            pass

        async def get_emby_config(self) -> Any:
            raise RuntimeError("simulated DB failure")

    def broken_factory() -> SettingsService:
        return _BrokenService()

    app.dependency_overrides[get_settings_service] = broken_factory
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            response = await c.get("/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["db_ok"] is False
        assert body["emby_configured"] is False
    finally:
        app.dependency_overrides.clear()
