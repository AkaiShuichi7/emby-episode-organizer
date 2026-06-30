"""媒体库 (Library) API 的 Pydantic 数据模型。

包含创建、更新、响应三类载荷。所有字段名 / 类型与 ORM ``Library`` 保持
一致，仅在 ``LibraryUpdate`` 把字段退化为可选，支持 PATCH 风格的局部更
新。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LibraryBase(BaseModel):
    """Library 共享字段集合，供 Create / Update 复用。

    Attributes:
        name: 媒体库展示名。
        collection_type: 媒体库类型（如 ``tvshows`` / ``movies``），可空。
        staging_root: 整理缓存根目录。
        target_root: Emby 实际挂载的目标根目录。
    """

    name: str
    collection_type: str | None = None
    staging_root: str
    target_root: str


class LibraryCreate(LibraryBase):
    """``POST /api/v1/libraries`` 请求载荷。

    Attributes:
        enabled: 是否启用该媒体库；默认 ``True``。
    """

    enabled: bool = True


class LibraryUpdate(BaseModel):
    """``PUT /api/v1/libraries/{id}`` 请求载荷。

    所有字段可选；调用方按需传入需要修改的字段，未传字段保持原值。
    """

    name: str | None = None
    collection_type: str | None = None
    staging_root: str | None = None
    target_root: str | None = None
    enabled: bool | None = None


class LibraryResponse(BaseModel):
    """``GET / POST / PUT /api/v1/libraries`` 响应载荷。

    Attributes:
        id: 数据库主键。
        emby_library_id: Emby 侧 Library ID（未关联时为空）。
        name: 媒体库展示名。
        collection_type: 媒体库类型。
        staging_root: 整理缓存根目录。
        target_root: 目标根目录。
        enabled: 是否启用。
        created_at: 创建时间。
        updated_at: 最后更新时间。
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    emby_library_id: str | None
    name: str
    collection_type: str | None
    staging_root: str | None
    target_root: str | None
    enabled: bool
    created_at: datetime
    updated_at: datetime
