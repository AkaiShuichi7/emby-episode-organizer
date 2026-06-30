"""设置服务。

以 ``settings`` 表为持久化载体，提供键值对的读取、写入、批量加载，以及
对 Emby 相关配置的强类型封装。

设计要点：
- value 列已声明为 JSON，因此 dict / list / str / bool / int 等任意可序列化
  结构都直接落库与读出，无需手动序列化。
- ``set`` 走 upsert（key 存在则更新 value，否则插入），靠 ``Setting.key`` 的
  ``unique`` 约束保证去重。
- ``get_emby_config`` 任一关键 key 缺失就返回 ``None``，让上层明确知道
  Emby 还未完成初始化，而不是拿到一个半残配置。
- ``init_default_settings`` 仅在 key 不存在时写入，幂等可重复执行；不会
  覆盖调用方已经改过的值。
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Setting

logger = logging.getLogger(__name__)


class EmbyConfig(BaseModel):
    """Emby 服务器连接配置。

    通过 ``server_url`` + ``api_key`` 访问 Emby；``auto_refresh`` 决定
    在整理完成后是否触发 Emby 库扫描。
    """

    server_url: str
    api_key: str
    auto_refresh: bool = False


# 默认配置：仅在 DB 为空时初始化写入，已存在的 key 不会被覆盖
DEFAULT_SETTINGS: dict[str, Any] = {
    "emby.auto_refresh": False,
    "file.source_mode": "copy",
    "file.allowed_browse_roots": ["/data"],
}

# EmbyConfig 涉及的三组 key，集中维护避免散落
_EMBY_KEYS: tuple[str, str, str] = (
    "emby.server_url",
    "emby.api_key",
    "emby.auto_refresh",
)


class SettingsService:
    """面向单次请求的设置读写服务。

    通过构造时注入 ``AsyncSession``，由调用方决定生命周期，便于在测试里
    直接使用内存 SQLite session。
    """

    def __init__(self, session: AsyncSession) -> None:
        """绑定本次请求使用的数据库会话。

        参数:
            session: 异步 SQLAlchemy 会话，由调用方负责提交与关闭。

        返回:
            None
        """
        self._session = session

    async def _find_by_key(self, key: str) -> Setting | None:
        """按业务 key（字符串）查找设置行，避开 session.get 的 PK 行为。"""
        result = await self._session.execute(
            select(Setting).where(Setting.key == key).limit(1)
        )
        return result.scalar_one_or_none()

    async def get(self, key: str) -> Any:
        """按 key 读取设置值。

        key 不存在时返回 ``None``，不抛异常；写入时如果是 dict / list 等
        复杂类型，DB 直接以 JSON 形式存储，这里读出即原值。

        参数:
            key: 设置项的字符串键。

        返回:
            任意 JSON 可序列化值；不存在则返回 ``None``。
        """
        row = await self._find_by_key(key)
        if row is None:
            return None
        return row.value

    async def set(self, key: str, value: Any) -> None:
        """写入或更新某个设置项（upsert 语义）。

        已存在的 key 走原地更新 value；不存在则新增一行。调用方负责提交
        会话。

        参数:
            key: 设置项的字符串键。
            value: 任意 JSON 可序列化值。

        返回:
            None
        """
        row = await self._find_by_key(key)
        if row is None:
            self._session.add(Setting(key=key, value=value))
        else:
            row.value = value

    async def get_all(self) -> dict[str, Any]:
        """一次性加载全部设置。

        以 ``{key: value}`` 形式返回；DB 为空时返回空字典。

        返回:
            所有设置项组成的字典。
        """
        result = await self._session.execute(select(Setting))
        rows = result.scalars().all()
        return {row.key: row.value for row in rows}

    async def get_emby_config(self) -> EmbyConfig | None:
        """读取 Emby 配置。

        三个关键 key 都齐全时构造 ``EmbyConfig`` 返回；任一缺失则返回
        ``None``，提示上层尚未完成 Emby 初始化。

        返回:
            完整的 ``EmbyConfig``；缺字段则返回 ``None``。
        """
        url = await self.get("emby.server_url")
        key = await self.get("emby.api_key")
        auto = await self.get("emby.auto_refresh")
        if url is None or key is None or auto is None:
            return None
        return EmbyConfig(server_url=url, api_key=key, auto_refresh=auto)

    async def set_emby_config(self, config: EmbyConfig) -> None:
        """写入 Emby 配置。

        将 ``server_url`` / ``api_key`` / ``auto_refresh`` 三个字段分别
        落到对应 key，调用方负责提交会话。

        参数:
            config: 待写入的 Emby 配置。

        返回:
            None
        """
        await self.set("emby.server_url", config.server_url)
        await self.set("emby.api_key", config.api_key)
        await self.set("emby.auto_refresh", config.auto_refresh)


async def init_default_settings(session: AsyncSession) -> None:
    """首次启动时写入默认设置项，幂等。

    仅当目标 key 在 DB 中不存在时才插入，不会覆盖调用方或运维已经修改
    过的值，因此可以放心重复调用。

    参数:
        session: 异步 SQLAlchemy 会话。

    返回:
        None
    """
    inserted = 0
    for key, value in DEFAULT_SETTINGS.items():
        result = await session.execute(
            select(Setting).where(Setting.key == key).limit(1)
        )
        if result.scalar_one_or_none() is not None:
            continue
        session.add(Setting(key=key, value=value))
        inserted += 1
    await session.commit()
    if inserted:
        logger.info("初始化默认设置完成，新写入 %d 项", inserted)
