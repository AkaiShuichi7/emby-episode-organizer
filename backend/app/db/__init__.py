"""数据库核心对象。

集中提供声明式基类 ``Base``、异步引擎 ``engine`` 与会话工厂 ``SessionLocal``，
供模型定义、初始化与业务层依赖注入复用。
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """所有 ORM 模型的声明式基类，承载统一的 metadata。"""

engine = create_async_engine(settings.database_url, echo=False)
"""进程级异步数据库引擎，连接由 settings.database_url 决定。"""

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
"""异步会话工厂，每次调用产出一个独立 AsyncSession。"""
