"""设置管理 API。

提供 ``GET /api/v1/settings`` 与 ``PUT /api/v1/settings`` 两组端点：

- ``GET`` 返回全部设置，敏感字段（``emby.api_key``）在响应层做 mask。
- ``PUT`` 整体覆盖式写入 key→value 字典，支持任意 JSON 可序列化值。

API Key 永远不在响应里明文回出；DB 中按 T12 设计保持明文存储（不做加密）。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import RootModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_settings_service
from app.api.v1 import api_v1_router
from app.services.settings import SettingsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])
"""设置路由，前缀 ``/settings``，挂载到 v1 总路由后实际路径为 ``/api/v1/settings``。"""


# 响应层需要 mask 的敏感字段。集中维护，避免散落到各端点逻辑里。
_MASKED_FIELDS: frozenset[str] = frozenset({"emby.api_key"})


def _mask_value(key: str, value: Any) -> Any:
    """对敏感字段做响应层 mask。

    仅对字符串值生效；空串/非字符串原样返回。长度 ``>= 4`` 时 mask 为
    ``xxxx****{last4}``，更短则整体替换为 ``****``。
    """
    if key not in _MASKED_FIELDS or not isinstance(value, str) or not value:
        return value
    if len(value) >= 4:
        return f"xxxx****{value[-4:]}"
    return "****"


class SettingsResponse(RootModel[dict[str, Any]]):
    """设置响应载荷 - 整体是一个 key→value 字典（敏感字段已被 mask）。"""


class SettingsUpdateRequest(RootModel[dict[str, Any]]):
    """设置更新请求载荷 - 整体是一个 key→value 字典。"""


@router.get("", response_model=SettingsResponse)
async def get_settings(
    service: SettingsService = Depends(get_settings_service),
) -> SettingsResponse:
    """读取全部设置，敏感字段自动 mask。

    返回:
        包含全部已存设置的字典；``emby.api_key`` 等敏感字段为 mask 形式。
    """
    raw = await service.get_all()
    masked = {k: _mask_value(k, v) for k, v in raw.items()}
    logger.info("读取设置 %d 项", len(masked))
    return SettingsResponse(root=masked)


@router.put("", response_model=SettingsResponse)
async def put_settings(
    body: SettingsUpdateRequest,
    service: SettingsService = Depends(get_settings_service),
    db: AsyncSession = Depends(get_db),
) -> SettingsResponse:
    """整体覆盖式写入设置。

    遍历请求体里的 key→value 写入 DB（upsert），写完显式 commit 以保证
    请求结束关闭 session 前数据落库。

    参数:
        body: 客户端提交的 key→value 字典，支持 dict / list / str / int / bool。
        service: 注入的设置服务实例。
        db: 与 service 共享的 session，用于显式 commit。

    返回:
        写入后的全量设置（敏感字段已 mask）。
    """
    payload = body.root
    for key, value in payload.items():
        await service.set(key, value)
    await db.commit()
    raw = await service.get_all()
    masked = {k: _mask_value(k, v) for k, v in raw.items()}
    logger.info("更新设置 %d 项", len(payload))
    return SettingsResponse(root=masked)


# 模块加载时自动挂载到 v1 总路由
api_v1_router.include_router(router)
