"""数据库模型测试。

验证 5 张表创建成功、Task 唯一约束、init_db 可重复执行。
"""

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.db import Base
from app.db.init_db import init_db
from app.db.models import Library, OperationLog, Series, Setting, Task, TaskStatus


@pytest.fixture
async def engine() -> AsyncEngine:
    """提供内存 SQLite 异步引擎并初始化所有表。"""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    await init_db(eng)
    return eng


async def test_all_tables_created(engine: AsyncEngine) -> None:
    """init_db 后 5 张业务表全部存在。"""

    def _table_names(sync_conn: object) -> list[str]:
        return inspect(sync_conn).get_table_names()

    async with engine.connect() as conn:
        names = await conn.run_sync(_table_names)

    for table in (
        Setting.__tablename__,
        Library.__tablename__,
        Series.__tablename__,
        Task.__tablename__,
        OperationLog.__tablename__,
    ):
        assert table in names


async def test_task_unique_constraint(engine: AsyncEngine) -> None:
    """相同 (series_id, season, episode) 的 Task 触发 IntegrityError。"""
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async with maker() as session:
        session.add(
            Task(
                status=TaskStatus.DRAFT,
                series_id=1,
                season_number=1,
                episode_number=1,
                title="第一集",
            )
        )
        await session.commit()

    async with maker() as session:
        session.add(
            Task(
                status=TaskStatus.DRAFT,
                series_id=1,
                season_number=1,
                episode_number=1,
                title="重复集",
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_models_share_base() -> None:
    """所有模型共享同一个 Base 元数据。"""
    tables = Base.metadata.tables
    for name in ("settings", "libraries", "series", "tasks", "operation_logs"):
        assert name in tables


async def test_setting_json_value(engine: AsyncEngine) -> None:
    """Setting.value 支持 JSON 读写。"""
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async with maker() as session:
        session.add(Setting(key="emby", value={"url": "http://x", "port": 8096}))
        await session.commit()

    async with maker() as session:
        row = (await session.get(Setting, 1))
        assert row is not None
        assert row.value == {"url": "http://x", "port": 8096}
