"""健康检查测试。"""

# pyright: reportMissingSuperCall=false

from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_settings_service
from app.main import app
from app.services.settings import SettingsService


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """裸 client（不注入 DB），用于 /health 兜底验证。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health(client: AsyncClient) -> None:
    """健康检查端点返回 ok + db_ok + emby_configured 三字段。"""
    response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    # DB 可达性 + Emby 配置状态都在响应里
    assert "db_ok" in body
    assert "emby_configured" in body


async def test_health_falls_back_when_settings_unavailable(
    client: AsyncClient,
) -> None:
    """settings 服务异常时 /health 仍 200，db_ok=false。"""

    class _BrokenService(SettingsService):
        """构造时不拿 session，``get_emby_config`` 直接抛错模拟 DB 故障。"""

        def __init__(self) -> None:  # noqa: D401 - test stub
            pass

        async def get_emby_config(self) -> Any:
            raise RuntimeError("simulated DB failure")

    def broken_factory() -> SettingsService:
        return _BrokenService()

    app.dependency_overrides[get_settings_service] = broken_factory
    try:
        response = await client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db_ok"] is False
    assert body["emby_configured"] is False
