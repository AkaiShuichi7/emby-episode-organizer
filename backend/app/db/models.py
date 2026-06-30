"""ORM 数据模型定义。

包含全局配置、媒体库、剧集、整理任务与操作日志五张核心表，是整个后端
业务状态的持久化载体。
"""

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TimestampMixin:
    """为模型补充创建 / 更新时间戳。

    created_at 在插入时写入，updated_at 在每次更新时自动刷新。
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )


class TaskStatus(enum.StrEnum):
    """整理任务状态机枚举。

    取值覆盖从草稿到落地 / 失败 / 取消的完整生命周期。
    """

    DRAFT = "draft"
    STAGED = "staged"
    NFO_EDITED = "nfo_edited"
    READY_TO_COMMIT = "ready_to_commit"
    COMMITTED = "committed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Setting(TimestampMixin, Base):
    """全局键值配置，value 以 JSON 存储任意结构。"""

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    value: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class Library(TimestampMixin, Base):
    """Emby 媒体库及其暂存 / 目标根目录配置。"""

    __tablename__ = "libraries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    emby_library_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    collection_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    staging_root: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    target_root: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Series(TimestampMixin, Base):
    """剧集元数据，归属某个媒体库，记录暂存 / 目标路径与默认季号。"""

    __tablename__ = "series"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    emby_series_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    library_id: Mapped[int | None] = mapped_column(
        ForeignKey("libraries.id"), nullable=True, index=True
    )
    library_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    staging_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    target_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    default_season: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Task(TimestampMixin, Base):
    """单集整理任务，串联源文件、暂存产物与目标落地路径及 NFO 数据。"""

    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint(
            "series_id", "season_number", "episode_number", name="uq_task_series_episode"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus), default=TaskStatus.DRAFT, nullable=False, index=True
    )
    series_id: Mapped[int | None] = mapped_column(
        ForeignKey("series.id"), nullable=True, index=True
    )
    series_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    emby_series_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    library_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    library_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    season_number: Mapped[int] = mapped_column(Integer, nullable=False)
    episode_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    staging_video_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    staging_nfo_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    staging_cover_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    target_video_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    target_nfo_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    target_cover_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    nfo_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class OperationLog(Base):
    """操作日志，记录动作、级别、消息与结构化明细。"""

    __tablename__ = "operation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(32), default="info", nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False, index=True
    )
