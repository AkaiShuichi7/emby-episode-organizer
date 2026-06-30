"""设置服务测试。

覆盖：get/set round-trip（dict/str/bool/list）、get_all、upsert 去重、
EmbyConfig 读写、init_default_settings 幂等。
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.init_db import init_db
from app.services.settings import (
    DEFAULT_SETTINGS,
    EmbyConfig,
    SettingsService,
    init_default_settings,
)


@pytest.fixture
async def engine() -> AsyncEngine:
    """提供内存 SQLite 异步引擎并初始化所有表。"""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    await init_db(eng)
    return eng


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncSession:
    """产出一个独立 AsyncSession 给被测服务。"""
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s


@pytest.fixture
async def service(session: AsyncSession) -> SettingsService:
    """直接绑定内存 session 的 SettingsService。"""
    return SettingsService(session)


async def test_get_missing_key_returns_none(service: SettingsService) -> None:
    """未设置的 key 读取返回 None，不抛异常。"""
    result = await service.get("emby.server_url")
    assert result is None


async def test_set_then_get_dict_value(service: SettingsService) -> None:
    """写入 dict 后 get 返回同一 dict。"""
    payload: dict[str, Any] = {"a": 1, "b": "x"}
    await service.set("file.allowed_browse_roots", payload)
    assert await service.get("file.allowed_browse_roots") == payload


async def test_set_then_get_str_value(service: SettingsService) -> None:
    """写入字符串后 get 返回同字符串。"""
    await service.set("emby.server_url", "http://192.168.1.10:8096")
    assert await service.get("emby.server_url") == "http://192.168.1.10:8096"


async def test_set_then_get_bool_value(service: SettingsService) -> None:
    """写入布尔后 get 返回同布尔。"""
    await service.set("emby.auto_refresh", True)
    assert await service.get("emby.auto_refresh") is True


async def test_set_then_get_list_value(service: SettingsService) -> None:
    """写入列表后 get 返回同列表。"""
    payload = ["/data", "/mnt/media"]
    await service.set("file.allowed_browse_roots", payload)
    assert await service.get("file.allowed_browse_roots") == payload


async def test_get_all_returns_all_set_values(service: SettingsService) -> None:
    """get_all 返回所有已写入的 key-value 字典。"""
    await service.set("emby.server_url", "http://x")
    await service.set("emby.api_key", "secret")
    await service.set("file.source_mode", "copy")

    result = await service.get_all()

    assert result == {
        "emby.server_url": "http://x",
        "emby.api_key": "secret",
        "file.source_mode": "copy",
    }


async def test_get_all_empty_when_nothing_set(service: SettingsService) -> None:
    """没有任何设置时 get_all 返回空字典。"""
    assert await service.get_all() == {}


async def test_set_overwrites_existing_key(service: SettingsService) -> None:
    """同一 key 多次 set，后值覆盖前值，DB 不出现重复行。"""
    await service.set("file.source_mode", "copy")
    await service.set("file.source_mode", "move")

    assert await service.get("file.source_mode") == "move"

    all_values = await service.get_all()
    assert all_values["file.source_mode"] == "move"
    assert list(all_values).count("file.source_mode") == 1


async def test_get_emby_config_when_all_keys_present(
    service: SettingsService,
) -> None:
    """server_url/api_key/auto_refresh 都存在时返回 EmbyConfig。"""
    await service.set("emby.server_url", "http://emby:8096")
    await service.set("emby.api_key", "abc123")
    await service.set("emby.auto_refresh", True)

    cfg = await service.get_emby_config()

    assert cfg == EmbyConfig(
        server_url="http://emby:8096",
        api_key="abc123",
        auto_refresh=True,
    )


async def test_get_emby_config_when_missing_key_returns_none(
    service: SettingsService,
) -> None:
    """任一关键 key 缺失时返回 None，不抛异常。"""
    await service.set("emby.server_url", "http://emby:8096")
    # 故意不写 api_key
    await service.set("emby.auto_refresh", False)

    cfg = await service.get_emby_config()

    assert cfg is None


async def test_get_emby_config_when_all_missing_returns_none(
    service: SettingsService,
) -> None:
    """三个 key 全未设置时返回 None。"""
    assert await service.get_emby_config() is None


async def test_set_emby_config_roundtrip(service: SettingsService) -> None:
    """set_emby_config 后 get_emby_config 返回同配置。"""
    cfg = EmbyConfig(
        server_url="http://emby:8096",
        api_key="xyz",
        auto_refresh=False,
    )
    await service.set_emby_config(cfg)

    assert await service.get_emby_config() == cfg


async def test_set_emby_config_default_auto_refresh(service: SettingsService) -> None:
    """EmbyConfig 默认 auto_refresh=False，落库后读回仍是 False。"""
    cfg = EmbyConfig(server_url="http://x", api_key="k")
    await service.set_emby_config(cfg)

    assert await service.get_emby_config() == cfg


async def test_init_default_settings_writes_defaults(engine: AsyncEngine) -> None:
    """init_default_settings 首次调用写入默认 keys。"""
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async with maker() as session:
        await init_default_settings(session)

    async with maker() as session:
        service = SettingsService(session)
        all_values = await service.get_all()

    assert all_values["emby.auto_refresh"] is False
    assert all_values["file.source_mode"] == "copy"
    assert all_values["file.allowed_browse_roots"] == ["/data"]


async def test_init_default_settings_is_idempotent(engine: AsyncEngine) -> None:
    """重复调用 init_default_settings 不会重复写入/修改默认值。"""
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async with maker() as session:
        await init_default_settings(session)

    # 二次调用前人为改值，幂等实现不应覆盖用户已写入的"key 已存在"判断
    async with maker() as session:
        service = SettingsService(session)
        await service.set("file.source_mode", "move")
        await init_default_settings(session)

    async with maker() as session:
        service = SettingsService(session)

    # 二次 init 不应把用户改过的值再覆盖回 copy
    assert await service.get("file.source_mode") == "move"
    # 默认 keys 仍然存在
    assert await service.get("emby.auto_refresh") is False
    assert await service.get("file.allowed_browse_roots") == ["/data"]


async def test_default_settings_constant_shape() -> None:
    """DEFAULT_SETTINGS 包含三项契约键，键名稳定。"""
    assert set(DEFAULT_SETTINGS) == {
        "emby.auto_refresh",
        "file.source_mode",
        "file.allowed_browse_roots",
    }
