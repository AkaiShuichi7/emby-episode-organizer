"""API 依赖注入。

统一对外暴露 ``get_db`` / ``get_settings_service`` / ``get_emby_config``，
由 FastAPI ``Depends`` 在每次请求时自动注入；测试可通过
``app.dependency_overrides`` 替换为 in-memory 实现。
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.services.settings import EmbyConfig, SettingsService


async def get_db() -> AsyncIterator[AsyncSession]:
    """为单次请求产出独立 ``AsyncSession``，请求结束自动关闭。

    使用 ``async with`` 保证异常路径也会正确释放连接；不会自动 commit，
    各路由按需手动提交。
    """
    async with SessionLocal() as session:
        yield session


def get_settings_service(
    db: AsyncSession = Depends(get_db),
) -> SettingsService:
    """构造绑定当前请求 session 的 ``SettingsService``。

    FastAPI 会对相同依赖做去重，因此 ``db`` 与 ``get_db`` 直接注入的会话
    是同一实例，可在路由内通过 ``db`` 显式 commit。
    """
    return SettingsService(db)


async def get_emby_config(
    service: SettingsService = Depends(get_settings_service),
) -> EmbyConfig | None:
    """读取当前 Emby 配置；任一关键 key 缺失则返回 ``None``。

    供后续 T15+ 业务接口复用，避免每个端点都重复从 settings 中凑字段。
    """
    return await service.get_emby_config()
