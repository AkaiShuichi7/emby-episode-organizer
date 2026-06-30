"""剧集 (Series) API 的 Pydantic 数据模型。

包含创建、更新、响应三类载荷。字段名 / 类型与 ORM ``Series`` 保持一致；
``SeriesUpdate`` 把字段退化为可选，支持 PATCH 风格的局部更新。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SeriesBase(BaseModel):
    """Series 共享字段集合，供 Create 复用。

    Attributes:
        name: 剧集展示名。
        library_id: 关联的媒体库主键；可空表示未关联。
        emby_series_id: Emby 侧 Series ID；可空。
        staging_path: 整理缓存路径；须落在关联 library 的 staging_root 下。
        target_path: Emby 实际挂载路径；须落在关联 library 的 target_root 下。
        default_season: 默认季号，默认 1。
    """

    name: str
    library_id: int | None = None
    emby_series_id: str | None = None
    staging_path: str | None = None
    target_path: str | None = None
    default_season: int = 1


class SeriesCreate(SeriesBase):
    """``POST /api/v1/series`` 请求载荷。

    Attributes:
        enabled: 是否启用该 series；默认 ``True``。
    """

    enabled: bool = True


class SeriesUpdate(BaseModel):
    """``PUT /api/v1/series/{id}`` 请求载荷。

    所有字段可选；调用方按需传入需要修改的字段，未传字段保持原值。
    """

    name: str | None = None
    library_id: int | None = None
    emby_series_id: str | None = None
    staging_path: str | None = None
    target_path: str | None = None
    default_season: int | None = None
    enabled: bool | None = None


class SeriesResponse(BaseModel):
    """``GET / POST / PUT /api/v1/series`` 响应载荷。

    Attributes:
        id: 数据库主键。
        emby_series_id: Emby 侧 Series ID。
        name: 剧集展示名。
        library_id: 关联的媒体库主键。
        library_name: 关联媒体库名称（冗余字段，便于列表展示）。
        staging_path: 整理缓存路径。
        target_path: 目标路径。
        default_season: 默认季号。
        enabled: 是否启用。
        created_at: 创建时间。
        updated_at: 最后更新时间。
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    emby_series_id: str | None
    name: str
    library_id: int | None
    library_name: str | None
    staging_path: str | None
    target_path: str | None
    default_season: int
    enabled: bool
    created_at: datetime
    updated_at: datetime
