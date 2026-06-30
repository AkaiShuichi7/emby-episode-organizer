"""数据库初始化。

提供 ``init_db`` 在应用启动时按声明式元数据创建全部表，幂等可重复执行。
"""

import logging

from sqlalchemy.ext.asyncio import AsyncEngine

# 导入 models 触发模型注册到 Base.metadata，勿删
from app.db import Base, engine, models  # noqa: F401

logger = logging.getLogger(__name__)


async def init_db(target_engine: AsyncEngine | None = None) -> None:
    """创建所有数据库表（已存在则跳过）。

    参数:
        target_engine: 指定的异步引擎；为空时使用默认 engine。便于测试注入内存库。

    返回:
        None
    """
    eng = target_engine or engine
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("数据库初始化完成，数据库表已创建")
