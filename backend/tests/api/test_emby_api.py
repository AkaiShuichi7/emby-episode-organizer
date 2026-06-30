"""Emby API 端到端测试。

覆盖：/test 连接测试、/libraries、/series/search、/series/{id}/seasons、
/series/{id}/seasons/{n}/episodes、/series/{id}/seasons/{n}/latest。

需要 Emby 配置的端点通过 ``app.dependency_overrides[get_emby_config]`` 注入
stub，避免依赖真实 DB 状态；``POST /test`` 直接读 body 的 server_url /
api_key，不依赖 ``get_emby_config``。HTTP 层通过 respx 拦截 Emby 客户端
发起的 httpx 调用。
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.api.deps import get_db, get_emby_config
from app.db import Base
from app.main import app
from app.services.settings import EmbyConfig, init_default_settings

# 测试统一使用的假 Emby 地址；respx 按 base_url 拦截所有发往这里的请求。
SERVER_URL = "http://emby.local:8096"
API_KEY = "test-api-key"


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
    """覆盖 ``get_db`` 到 in-memory 并初始化默认设置，包装 ASGI 客户端。"""
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


@pytest.fixture
async def client_with_emby(client: AsyncClient) -> AsyncIterator[AsyncClient]:
    """在 ``client`` 基础上额外注入 Emby 配置 stub，使 ``get_emby_config`` 直接返回。"""
    config = EmbyConfig(server_url=SERVER_URL, api_key=API_KEY, auto_refresh=False)

    def stub_config() -> EmbyConfig:
        return config

    app.dependency_overrides[get_emby_config] = stub_config
    yield client
    # 由 ``client`` fixture 在 teardown 时统一清空 overrides


async def test_post_test_returns_success_when_connected(client: AsyncClient) -> None:
    """``POST /api/v1/emby/test`` 在 Emby 公共信息接口返回 200 时 success=true。"""
    with respx.mock(base_url=SERVER_URL) as mock:
        route = mock.get("/System/Info/Public").respond(200, json={"ServerName": "MyEmby"})
        response = await client.post(
            "/api/v1/emby/test",
            json={"server_url": SERVER_URL, "api_key": API_KEY},
        )

    assert route.called
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True


async def test_post_test_returns_api_key_error_on_401(client: AsyncClient) -> None:
    """``POST /api/v1/emby/test`` 在 Emby 返回 401 时 message 含 ``API Key``。"""
    with respx.mock(base_url=SERVER_URL) as mock:
        _ = mock.get("/System/Info/Public").respond(401, json={"Message": "Unauthorized"})
        response = await client.post(
            "/api/v1/emby/test",
            json={"server_url": SERVER_URL, "api_key": "bad-key"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert "API Key" in body["message"]


async def test_post_test_returns_connection_error_on_network_failure(
    client: AsyncClient,
) -> None:
    """``POST /api/v1/emby/test`` 在 Emby 不可达时 message 含 ``连接``。"""
    with respx.mock(base_url=SERVER_URL) as mock:
        _ = mock.get("/System/Info/Public").mock(
            side_effect=httpx.ConnectError("simulated unreachable"),
        )
        response = await client.post(
            "/api/v1/emby/test",
            json={"server_url": SERVER_URL, "api_key": API_KEY},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert "连接" in body["message"]


async def test_libraries_returns_400_when_emby_not_configured(
    client: AsyncClient,
) -> None:
    """``GET /api/v1/emby/libraries`` 在未配置 Emby 时返回 400 + 未配置消息。"""
    response = await client.get("/api/v1/emby/libraries")

    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert "未配置" in body["message"]


async def test_libraries_returns_two_libraries_when_configured(
    client_with_emby: AsyncClient,
) -> None:
    """``GET /api/v1/emby/libraries`` 在配置齐全 + 接口返回 2 个媒体库时透传 2 项。"""
    payload = {
        "Items": [
            {"ItemId": "lib-tv", "Name": "电视剧", "CollectionType": "tvshows"},
            {"ItemId": "lib-anime", "Name": "动画", "CollectionType": "tvshows"},
        ]
    }
    with respx.mock(base_url=SERVER_URL) as mock:
        route = mock.get("/Library/MediaFolders").respond(200, json=payload)
        response = await client_with_emby.get("/api/v1/emby/libraries")

    assert route.called
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["Name"] == "电视剧"
    assert body[1]["CollectionType"] == "tvshows"


async def test_series_search_returns_matches(client_with_emby: AsyncClient) -> None:
    """``GET /api/v1/emby/series/search?keyword=X`` 透传 Emby ``/Items`` 搜索结果。"""
    payload = {
        "Items": [
            {"Id": "s1", "Name": "孤独摇滚", "LibraryName": "动画"},
            {"Id": "s2", "Name": "摇滚乃淑女的爱好", "LibraryName": "动画"},
        ]
    }
    with respx.mock(base_url=SERVER_URL) as mock:
        route = mock.get("/Items").respond(200, json=payload)
        response = await client_with_emby.get(
            "/api/v1/emby/series/search",
            params={"keyword": "摇滚"},
        )

    assert route.called
    assert route.calls.last.request.url.params["SearchTerm"] == "摇滚"
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["Name"] == "孤独摇滚"


async def test_series_seasons_returns_list(client_with_emby: AsyncClient) -> None:
    """``GET /api/v1/emby/series/{id}/seasons`` 透传 Emby 季列表。"""
    payload = {
        "Items": [
            {"Id": "season-1", "IndexNumber": 1, "Name": "Season 1"},
            {"Id": "season-2", "IndexNumber": 2, "Name": "Season 2"},
        ]
    }
    with respx.mock(base_url=SERVER_URL) as mock:
        route = mock.get("/Shows/series-1/Seasons").respond(200, json=payload)
        response = await client_with_emby.get("/api/v1/emby/series/series-1/seasons")

    assert route.called
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["IndexNumber"] == 1
    assert body[1]["Name"] == "Season 2"


async def test_series_episodes_returns_list(client_with_emby: AsyncClient) -> None:
    """``GET /api/v1/emby/series/{id}/seasons/{n}/episodes`` 透传分集列表。"""
    payload = {
        "Items": [
            {"Id": "ep-1", "IndexNumber": 1, "Name": "第一集", "SeriesId": "series-1"},
            {"Id": "ep-2", "IndexNumber": 2, "Name": "第二集", "SeriesId": "series-1"},
        ]
    }
    with respx.mock(base_url=SERVER_URL) as mock:
        route = mock.get("/Shows/series-1/Episodes").respond(200, json=payload)
        response = await client_with_emby.get(
            "/api/v1/emby/series/series-1/seasons/1/episodes",
        )

    assert route.called
    assert route.calls.last.request.url.params["Season"] == "1"
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2


async def test_series_latest_returns_latest_and_next(client_with_emby: AsyncClient) -> None:
    """``GET /api/v1/emby/series/{id}/seasons/1/latest`` 返回 ``{latest, next}``。"""
    payload = {
        "Items": [
            {"Id": "ep-1", "IndexNumber": 1, "Name": "第一集", "SeriesId": "series-1"},
            {"Id": "ep-2", "IndexNumber": 2, "Name": "第二集", "SeriesId": "series-1"},
            {"Id": "ep-3", "IndexNumber": 3, "Name": "第三集", "SeriesId": "series-1"},
        ]
    }
    with respx.mock(base_url=SERVER_URL) as mock:
        route = mock.get("/Shows/series-1/Episodes").respond(200, json=payload)
        response = await client_with_emby.get(
            "/api/v1/emby/series/series-1/seasons/1/latest",
        )

    assert route.called
    assert response.status_code == 200
    body = response.json()
    assert body["latest_episode"] == 3
    assert body["next_episode"] == 4
