"""Emby API 客户端。

负责用异步 httpx 调 Emby REST API，处理连接、鉴权、基础错误映射，
并把常用列表响应转换成 Pydantic 模型。
"""

from __future__ import annotations

import logging
from typing import cast

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

type JsonDict = dict[str, object]


class EmbyLibrary(BaseModel):
    """Emby 媒体库。

    Attributes:
        ItemId: 媒体库唯一 ID。
        Name: 媒体库名称。
        CollectionType: 媒体库类型，如 tvshows。
    """

    ItemId: str
    Name: str
    CollectionType: str | None = None


class EmbySeries(BaseModel):
    """Emby 剧集搜索结果。

    Attributes:
        Id: 剧集 ID。
        Name: 剧集名称。
        LibraryName: 所属媒体库名称。
    """

    Id: str
    Name: str
    LibraryName: str | None = None


class EmbySeason(BaseModel):
    """Emby 季信息。

    Attributes:
        Id: 季 ID。
        IndexNumber: 季号。
        Name: 季名称。
    """

    Id: str
    IndexNumber: int
    Name: str


class EmbyEpisode(BaseModel):
    """Emby 分集信息。

    Attributes:
        Id: 分集 ID。
        IndexNumber: 集号。
        Name: 分集名称。
        SeriesId: 所属剧集 ID。
    """

    Id: str
    IndexNumber: int
    Name: str
    SeriesId: str


class EmbyConnectionError(Exception):
    """Emby 连接失败或返回非预期状态码时抛出。"""


class EmbyAuthError(Exception):
    """Emby API Key 无效或权限不足时抛出。"""


class EmbyNotFoundError(Exception):
    """Emby 资源不存在时抛出。"""


class EmbyClient:
    """Emby REST API 最小客户端。

    Args:
        server_url: Emby 服务根地址。
        api_key: Emby API Key。
        timeout: 请求超时秒数。
        client: 可选注入 httpx.AsyncClient，便于测试。
    """

    def __init__(
        self,
        server_url: str,
        api_key: str,
        timeout: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._server_url: str = server_url.rstrip("/")
        self._timeout: float = timeout
        self._owns_client: bool = client is None

        if client is None:
            actual_client = httpx.AsyncClient(
                base_url=self._server_url,
                headers={"X-Emby-Token": api_key, "Accept": "application/json"},
                timeout=timeout,
            )
        else:
            client.headers.update({"X-Emby-Token": api_key, "Accept": "application/json"})
            actual_client = client

        self._client: httpx.AsyncClient = actual_client

    def _build_url(self, path: str) -> str:
        """拼完整请求 URL。"""
        return f"{self._server_url}{path}"

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str | int] | None = None,
    ) -> JsonDict:
        """发送 JSON 请求并把常见状态码映射为业务异常。

        Args:
            method: HTTP 方法。
            path: 相对 API 路径。
            params: 查询参数。

        Returns:
            解析后的 JSON 字典。

        Raises:
            EmbyAuthError: 401/403。
            EmbyNotFoundError: 404。
            EmbyConnectionError: 其它网络错误或非 2xx。
        """
        url = self._build_url(path)

        try:
            response = await self._client.request(method, url, params=params)
        except httpx.HTTPError as exc:
            logger.error("Emby 请求失败: method=%s url=%s err=%s", method, url, exc)
            raise EmbyConnectionError(f"Emby 请求失败: {exc}") from exc

        if response.status_code in {401, 403}:
            logger.warning(
                "Emby 鉴权失败: method=%s url=%s status=%d",
                method,
                url,
                response.status_code,
            )
            raise EmbyAuthError(f"Emby 鉴权失败: HTTP {response.status_code}")

        if response.status_code == 404:
            logger.warning("Emby 资源不存在: method=%s url=%s", method, url)
            raise EmbyNotFoundError(f"Emby 资源不存在: {path}")

        if response.is_error:
            logger.error(
                "Emby 响应异常: method=%s url=%s status=%d",
                method,
                url,
                response.status_code,
            )
            raise EmbyConnectionError(f"Emby 响应异常: HTTP {response.status_code}")

        payload: object = response.json()  # pyright: ignore[reportAny]
        if not isinstance(payload, dict):
            logger.error("Emby JSON 响应不是对象: method=%s url=%s", method, url)
            raise EmbyConnectionError("Emby JSON 响应格式错误")

        return cast(JsonDict, payload)

    @staticmethod
    def _items(payload: JsonDict) -> list[JsonDict]:
        """提取列表响应里的 Items。"""
        items_obj = payload.get("Items", [])
        if not isinstance(items_obj, list):
            return []

        items: list[JsonDict] = []
        for item_obj in cast(list[object], items_obj):
            if isinstance(item_obj, dict):
                items.append(cast(JsonDict, item_obj))
        return items

    async def test_connection(self) -> bool:
        """测试 Emby 连接是否可用。

        Returns:
            连接成功返回 True。

        Raises:
            EmbyAuthError: API Key 无效或无权限。
            EmbyConnectionError: 服务不可达或返回非 2xx。
        """
        try:
            response = await self._client.get(self._build_url("/System/Info/Public"))
        except httpx.HTTPError as exc:
            logger.error(
                "Emby 连接测试失败: url=%s err=%s",
                self._build_url("/System/Info/Public"),
                exc,
            )
            raise EmbyConnectionError(f"Emby 连接失败: {exc}") from exc

        if response.status_code in {401, 403}:
            logger.warning("Emby 连接测试鉴权失败: status=%d", response.status_code)
            raise EmbyAuthError(f"Emby 鉴权失败: HTTP {response.status_code}")

        if response.is_error:
            logger.error("Emby 连接测试返回异常状态: status=%d", response.status_code)
            raise EmbyConnectionError(f"Emby 连接失败: HTTP {response.status_code}")

        logger.info("Emby 连接测试成功: server=%s", self._server_url)
        return True

    async def get_libraries(self) -> list[EmbyLibrary]:
        """获取 Emby 媒体库列表。"""
        payload = await self._request_json("GET", "/Library/MediaFolders")
        libraries = [EmbyLibrary.model_validate(item) for item in self._items(payload)]
        logger.info("获取 Emby 媒体库成功: count=%d", len(libraries))
        return libraries

    async def search_series(self, keyword: str) -> list[EmbySeries]:
        """按关键字搜索剧集。"""
        payload = await self._request_json(
            "GET",
            "/Items",
            params={"SearchTerm": keyword, "IncludeItemTypes": "Series", "Recursive": "true"},
        )
        series_list = [EmbySeries.model_validate(item) for item in self._items(payload)]
        logger.info("搜索 Emby 剧集成功: keyword=%s count=%d", keyword, len(series_list))
        return series_list

    async def get_seasons(self, series_id: str) -> list[EmbySeason]:
        """获取指定剧集的季列表。"""
        payload = await self._request_json("GET", f"/Shows/{series_id}/Seasons")
        seasons = [EmbySeason.model_validate(item) for item in self._items(payload)]
        logger.info("获取 Emby 季列表成功: series_id=%s count=%d", series_id, len(seasons))
        return seasons

    async def get_episodes(self, series_id: str, season_number: int) -> list[EmbyEpisode]:
        """获取指定剧集指定季的分集列表。

        缺少 ``IndexNumber`` 的条目会忽略，因为无法参与下一集号推断。
        """
        payload = await self._request_json(
            "GET",
            f"/Shows/{series_id}/Episodes",
            params={"Season": season_number},
        )

        episodes: list[EmbyEpisode] = []
        for item in self._items(payload):
            if item.get("IndexNumber") is None:
                logger.info(
                    "忽略缺少集号的 Emby 分集: series_id=%s season=%d item_id=%s",
                    series_id,
                    season_number,
                    item.get("Id"),
                )
                continue
            episodes.append(EmbyEpisode.model_validate(item))

        logger.info(
            "获取 Emby 分集成功: series_id=%s season=%d count=%d",
            series_id,
            season_number,
            len(episodes),
        )
        return episodes

    async def get_latest_episode(self, series_id: str, season_number: int) -> int:
        """返回下一可用集号。

        无任何有效分集时返回 1；否则返回最大 ``IndexNumber`` + 1。
        """
        episodes = await self.get_episodes(series_id, season_number)
        if not episodes:
            logger.info(
                "Emby 季为空，下一集默认 1: series_id=%s season=%d",
                series_id,
                season_number,
            )
            return 1

        latest = max(episode.IndexNumber for episode in episodes) + 1
        logger.info(
            "推断下一集号成功: series_id=%s season=%d next_episode=%d",
            series_id,
            season_number,
            latest,
        )
        return latest

    async def aclose(self) -> None:
        """关闭内部 httpx 客户端。"""
        if self._owns_client:
            await self._client.aclose()
