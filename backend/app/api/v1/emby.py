"""Emby 集成 API。

提供 Emby 连接测试、媒体库查询、剧集搜索、季/分集信息查询等端点。
错误响应遵循统一格式 ``{success: bool, message: str, detail: str | None}``：

- 业务错误（未配置 Emby）→ 400 + 错误体；
- ``/test`` 端点的鉴权/连接失败 → 200 + ``success=false``，前端按
  ``success`` 字段判定而不依赖 HTTP 状态码；
- 未预期的代码异常 → 500，由 FastAPI 默认处理。

业务依赖的 ``EmbyClient`` 由各端点按请求实例化 + ``aclose``，避免长生命
周期 httpx 客户端在测试间串扰。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_emby_config
from app.api.v1 import api_v1_router
from app.db.models import TaskStatus
from app.services.emby import (
    EmbyAuthError,
    EmbyClient,
    EmbyConnectionError,
)
from app.services.settings import EmbyConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/emby", tags=["emby"])
"""Emby 集成路由，前缀 ``/emby``，挂载到 v1 总路由后实际路径为 ``/api/v1/emby``。"""


class EmbyTestRequest(BaseModel):
    """``POST /emby/test`` 请求载荷。

    Attributes:
        server_url: Emby 服务器根地址。
        api_key: Emby API Key。
    """

    server_url: str
    api_key: str


class EmbyTestResponse(BaseModel):
    """``POST /emby/test`` 响应载荷。

    Attributes:
        success: 是否连接成功。
        message: 中文提示消息。
        server_name: Emby 服务名（保留字段，目前不强制填充）。
    """

    success: bool
    message: str
    server_name: str | None = None


class ErrorResponse(BaseModel):
    """统一错误响应载荷。

    Attributes:
        success: 固定 False。
        message: 简短中文提示。
        detail: 可选的详细错误信息（如异常文本）。
    """

    success: bool = False
    message: str
    detail: str | None = None


class LatestEpisodeResponse(BaseModel):
    """下一集号推断响应。

    Attributes:
        latest_episode: 当前最大集号；季内无任何分集时为 0。
        next_episode: 应使用的下一集号，``latest_episode + 1``；季内无分集时为 1。
    """

    latest_episode: int
    next_episode: int


def _not_configured_response() -> JSONResponse:
    """构造「未配置 Emby」的 400 错误响应。"""
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(message="未配置 Emby").model_dump(),
    )


def _make_client(config: EmbyConfig) -> EmbyClient:
    """从 ``EmbyConfig`` 构造 ``EmbyClient``。"""
    return EmbyClient(config.server_url, config.api_key)


@router.post("/test", response_model=EmbyTestResponse)
async def test_emby_connection(body: EmbyTestRequest) -> EmbyTestResponse | JSONResponse:
    """测试给定的 Emby 服务是否可达。

    参数:
        body: 包含 ``server_url`` 与 ``api_key`` 的请求体。

    返回:
        - 成功：``{success: true, message: "连接成功"}``；
        - 鉴权失败：``{success: false, message: "API Key 无效"}``；
        - 连接失败：``{success: false, message: "连接失败"}``；
        - 未预期异常：500 + 错误体。

    说明:
        鉴权/连接失败仍返回 200 + ``success=false``，避免前端按 HTTP 状态
        码区分业务失败与系统故障。
    """
    client = EmbyClient(body.server_url, body.api_key)
    try:
        await client.test_connection()
    except EmbyAuthError:
        logger.warning("Emby 测试连接鉴权失败: server=%s", body.server_url)
        return EmbyTestResponse(success=False, message="API Key 无效")
    except EmbyConnectionError as exc:
        logger.warning("Emby 测试连接失败: server=%s err=%s", body.server_url, exc)
        return EmbyTestResponse(success=False, message="连接失败")
    except Exception as exc:
        # 未预期异常 → 500 + 统一错误体（真正的代码 bug 路径）
        logger.exception("Emby 测试连接未知错误: server=%s", body.server_url)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(message="未知错误", detail=str(exc)).model_dump(),
        )
    finally:
        await client.aclose()

    logger.info("Emby 测试连接成功: server=%s", body.server_url)
    return EmbyTestResponse(success=True, message="连接成功")


@router.get("/libraries", response_model=list[Any])
async def get_libraries(
    config: EmbyConfig | None = Depends(get_emby_config),
) -> JSONResponse | list[dict[str, Any]]:
    """获取 Emby 媒体库列表。

    返回:
        未配置 Emby → 400 + 错误体；成功 → ``[EmbyLibrary, ...]``。
    """
    if config is None:
        return _not_configured_response()

    client = _make_client(config)
    try:
        libraries = await client.get_libraries()
    finally:
        await client.aclose()

    return [library.model_dump() for library in libraries]


@router.get("/series/search", response_model=list[Any])
async def search_series(
    keyword: str = Query(..., description="剧集搜索关键字"),
    config: EmbyConfig | None = Depends(get_emby_config),
) -> JSONResponse | list[dict[str, Any]]:
    """按关键字搜索 Emby 剧集。"""
    if config is None:
        return _not_configured_response()

    client = _make_client(config)
    try:
        results = await client.search_series(keyword)
    finally:
        await client.aclose()

    return [series.model_dump() for series in results]


@router.get("/series/{series_id}/seasons", response_model=list[Any])
async def get_series_seasons(
    series_id: str,
    config: EmbyConfig | None = Depends(get_emby_config),
) -> JSONResponse | list[dict[str, Any]]:
    """获取指定剧集的季列表。"""
    if config is None:
        return _not_configured_response()

    client = _make_client(config)
    try:
        seasons = await client.get_seasons(series_id)
    finally:
        await client.aclose()

    return [season.model_dump() for season in seasons]


@router.get(
    "/series/{series_id}/seasons/{season_number}/episodes",
    response_model=list[Any],
)
async def get_series_episodes(
    series_id: str,
    season_number: int,
    config: EmbyConfig | None = Depends(get_emby_config),
) -> JSONResponse | list[dict[str, Any]]:
    """获取指定剧集指定季的分集列表。"""
    if config is None:
        return _not_configured_response()

    client = _make_client(config)
    try:
        episodes = await client.get_episodes(series_id, season_number)
    finally:
        await client.aclose()

    return [episode.model_dump() for episode in episodes]


@router.get(
    "/series/{series_id}/seasons/{season_number}/latest",
    response_model=LatestEpisodeResponse,
)
async def get_series_latest_episode(
    series_id: str,
    season_number: int,
    config: EmbyConfig | None = Depends(get_emby_config),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse | LatestEpisodeResponse:
    """推断指定剧集指定季的下一可用集号。

    返回:
        - 未配置 Emby → 400；
        - 季内无分集且本地无非终态任务 → ``{latest_episode: 0, next_episode: 1}``；
        - 有分集或本地存在非终态任务 → ``{latest_episode: max, next_episode: max + 1}``。
    """
    if config is None:
        return _not_configured_response()

    client = _make_client(config)
    try:
        episodes = await client.get_episodes(series_id, season_number)
    finally:
        await client.aclose()

    emby_latest = max((episode.IndexNumber for episode in episodes), default=0)

    try:
        result = await db.execute(
            text(
                "SELECT MAX(episode_number) AS max_episode "
                "FROM tasks "
                "WHERE emby_series_id = :sid "
                "AND season_number = :season "
                "AND status NOT IN (:committed, :cancelled)"
            ),
            {
                "sid": series_id,
                "season": season_number,
                "committed": TaskStatus.COMMITTED.value,
                "cancelled": TaskStatus.CANCELLED.value,
            },
        )
        local_latest = result.scalar_one_or_none() or 0
    except Exception:
        # ponytail: 本地 tasks 查询失败时回退 Emby 最大集号，避免 latest 接口被 DB 问题拖死。
        logger.warning("Emby 最新集号查询本地任务失败，回退 Emby 数据: series_id=%s season=%s", series_id, season_number, exc_info=True)
        local_latest = 0

    latest = max(emby_latest, local_latest)
    logger.info(
        "Emby 最新集号计算完成: series_id=%s season=%s emby_latest=%s local_latest=%s latest=%s next=%s",
        series_id,
        season_number,
        emby_latest,
        local_latest,
        latest,
        latest + 1,
    )
    return LatestEpisodeResponse(latest_episode=latest, next_episode=latest + 1)


# 模块加载时自动挂载到 v1 总路由
api_v1_router.include_router(router)
