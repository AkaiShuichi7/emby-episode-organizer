"""Emby API 客户端测试。

覆盖：连接鉴权、媒体库查询、剧集搜索、季列表、分集过滤、最新集数推断。
"""

from __future__ import annotations

import httpx
import pytest
import respx

from app.services.emby import (
    EmbyAuthError,
    EmbyClient,
    EmbyConnectionError,
    EmbyEpisode,
    EmbyLibrary,
    EmbySeason,
    EmbySeries,
)


async def test_connection_returns_true_on_200() -> None:
    """公共信息接口 200 时返回 True。"""
    async with httpx.AsyncClient(base_url="http://emby.local:8096") as http_client:
        with respx.mock(base_url="http://emby.local:8096") as mock:
            route = mock.get("/System/Info/Public").respond(200, json={"ServerName": "Emby"})
            client = EmbyClient("http://emby.local:8096", "secret", client=http_client)

            result = await client.test_connection()

    assert route.called
    assert result is True


async def test_connection_raises_auth_error_on_401() -> None:
    """鉴权失败时抛 EmbyAuthError。"""
    async with httpx.AsyncClient(base_url="http://emby.local:8096") as http_client:
        with respx.mock(base_url="http://emby.local:8096") as mock:
            _ = mock.get("/System/Info/Public").respond(401, json={"Message": "Unauthorized"})
            client = EmbyClient("http://emby.local:8096", "bad-key", client=http_client)

            with pytest.raises(EmbyAuthError):
                _ = await client.test_connection()


async def test_connection_raises_connection_error_on_500() -> None:
    """服务端错误时抛 EmbyConnectionError。"""
    async with httpx.AsyncClient(base_url="http://emby.local:8096") as http_client:
        with respx.mock(base_url="http://emby.local:8096") as mock:
            _ = mock.get("/System/Info/Public").respond(500, json={"Message": "boom"})
            client = EmbyClient("http://emby.local:8096", "secret", client=http_client)

            with pytest.raises(EmbyConnectionError):
                _ = await client.test_connection()


async def test_get_libraries_returns_two_libraries() -> None:
    """媒体库列表接口返回 Items 并映射为 EmbyLibrary。"""
    payload = {
        "Items": [
            {"ItemId": "lib-tv", "Name": "电视剧", "CollectionType": "tvshows"},
            {"ItemId": "lib-anime", "Name": "动画", "CollectionType": "tvshows"},
        ]
    }

    async with httpx.AsyncClient(base_url="http://emby.local:8096") as http_client:
        with respx.mock(base_url="http://emby.local:8096") as mock:
            _ = mock.get("/Library/MediaFolders").respond(200, json=payload)
            client = EmbyClient("http://emby.local:8096", "secret", client=http_client)

            libraries = await client.get_libraries()

    assert libraries == [
        EmbyLibrary(ItemId="lib-tv", Name="电视剧", CollectionType="tvshows"),
        EmbyLibrary(ItemId="lib-anime", Name="动画", CollectionType="tvshows"),
    ]


async def test_search_series_returns_matches() -> None:
    """搜索剧集时只映射需要字段。"""
    payload = {
        "Items": [
            {"Id": "s1", "Name": "孤独摇滚", "LibraryName": "动画"},
            {"Id": "s2", "Name": "摇滚乃淑女的爱好", "LibraryName": "动画"},
        ]
    }

    async with httpx.AsyncClient(base_url="http://emby.local:8096") as http_client:
        with respx.mock(base_url="http://emby.local:8096") as mock:
            route = mock.get("/Items").respond(200, json=payload)
            client = EmbyClient("http://emby.local:8096", "secret", client=http_client)

            series_list = await client.search_series("摇滚")

    request = route.calls.last.request
    assert request.url.params["SearchTerm"] == "摇滚"
    assert request.url.params["IncludeItemTypes"] == "Series"
    assert request.url.params["Recursive"] == "true"
    assert series_list == [
        EmbySeries(Id="s1", Name="孤独摇滚", LibraryName="动画"),
        EmbySeries(Id="s2", Name="摇滚乃淑女的爱好", LibraryName="动画"),
    ]


async def test_get_seasons_returns_items() -> None:
    """季列表接口映射为 EmbySeason。"""
    payload = {
        "Items": [
            {"Id": "season-1", "IndexNumber": 1, "Name": "Season 1"},
            {"Id": "season-2", "IndexNumber": 2, "Name": "Season 2"},
        ]
    }

    async with httpx.AsyncClient(base_url="http://emby.local:8096") as http_client:
        with respx.mock(base_url="http://emby.local:8096") as mock:
            _ = mock.get("/Shows/series-1/Seasons").respond(200, json=payload)
            client = EmbyClient("http://emby.local:8096", "secret", client=http_client)

            seasons = await client.get_seasons("series-1")

    assert seasons == [
        EmbySeason(Id="season-1", IndexNumber=1, Name="Season 1"),
        EmbySeason(Id="season-2", IndexNumber=2, Name="Season 2"),
    ]


async def test_get_episodes_ignores_missing_index_number() -> None:
    """缺少 IndexNumber 的条目必须忽略。"""
    payload = {
        "Items": [
            {"Id": "ep-1", "IndexNumber": 1, "Name": "第一集", "SeriesId": "series-1"},
            {"Id": "ep-x", "Name": "特别篇", "SeriesId": "series-1"},
            {"Id": "ep-2", "IndexNumber": 2, "Name": "第二集", "SeriesId": "series-1"},
        ]
    }

    async with httpx.AsyncClient(base_url="http://emby.local:8096") as http_client:
        with respx.mock(base_url="http://emby.local:8096") as mock:
            route = mock.get("/Shows/series-1/Episodes").respond(200, json=payload)
            client = EmbyClient("http://emby.local:8096", "secret", client=http_client)

            episodes = await client.get_episodes("series-1", 1)

    request = route.calls.last.request
    assert request.url.params["Season"] == "1"
    assert episodes == [
        EmbyEpisode(Id="ep-1", IndexNumber=1, Name="第一集", SeriesId="series-1"),
        EmbyEpisode(Id="ep-2", IndexNumber=2, Name="第二集", SeriesId="series-1"),
    ]


async def test_get_episodes_returns_empty_when_all_missing_index_number() -> None:
    """全部缺少 IndexNumber 时返回空列表。"""
    payload = {
        "Items": [
            {"Id": "ep-x", "Name": "特别篇", "SeriesId": "series-1"},
            {"Id": "ep-y", "Name": "花絮", "SeriesId": "series-1"},
        ]
    }

    async with httpx.AsyncClient(base_url="http://emby.local:8096") as http_client:
        with respx.mock(base_url="http://emby.local:8096") as mock:
            _ = mock.get("/Shows/series-1/Episodes").respond(200, json=payload)
            client = EmbyClient("http://emby.local:8096", "secret", client=http_client)

            episodes = await client.get_episodes("series-1", 1)

    assert episodes == []


async def test_get_latest_episode_returns_next_index_after_max() -> None:
    """已有 1,2,3 集时返回下一集 4。"""
    payload = {
        "Items": [
            {"Id": "ep-1", "IndexNumber": 1, "Name": "第一集", "SeriesId": "series-1"},
            {"Id": "ep-2", "IndexNumber": 2, "Name": "第二集", "SeriesId": "series-1"},
            {"Id": "ep-3", "IndexNumber": 3, "Name": "第三集", "SeriesId": "series-1"},
        ]
    }

    async with httpx.AsyncClient(base_url="http://emby.local:8096") as http_client:
        with respx.mock(base_url="http://emby.local:8096") as mock:
            _ = mock.get("/Shows/series-1/Episodes").respond(200, json=payload)
            client = EmbyClient("http://emby.local:8096", "secret", client=http_client)

            latest = await client.get_latest_episode("series-1", 1)

    assert latest == 4


async def test_get_latest_episode_returns_one_when_no_episode() -> None:
    """空季返回第一集编号 1。"""
    async with httpx.AsyncClient(base_url="http://emby.local:8096") as http_client:
        with respx.mock(base_url="http://emby.local:8096") as mock:
            _ = mock.get("/Shows/series-1/Episodes").respond(200, json={"Items": []})
            client = EmbyClient("http://emby.local:8096", "secret", client=http_client)

            latest = await client.get_latest_episode("series-1", 1)

    assert latest == 1


async def test_get_latest_episode_returns_next_index_for_single_episode() -> None:
    """只有第 5 集时返回 6。"""
    payload = {
        "Items": [
            {"Id": "ep-5", "IndexNumber": 5, "Name": "第五集", "SeriesId": "series-1"}
        ]
    }

    async with httpx.AsyncClient(base_url="http://emby.local:8096") as http_client:
        with respx.mock(base_url="http://emby.local:8096") as mock:
            _ = mock.get("/Shows/series-1/Episodes").respond(200, json=payload)
            client = EmbyClient("http://emby.local:8096", "secret", client=http_client)

            latest = await client.get_latest_episode("series-1", 1)

    assert latest == 6
