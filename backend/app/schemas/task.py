"""任务 (Task) API 的 Pydantic 数据模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.db.models import TaskStatus


class TaskPreviewRequest(BaseModel):
    """任务路径预览请求。"""

    series_id: int
    season_number: int
    episode_number: int | None = None
    title: str = ""
    source_file_path: str
    cover_url: str | None = None


class TaskPreviewResponse(BaseModel):
    """任务路径预览响应。"""

    series_id: int
    season_number: int
    episode_number: int | None = None
    title: str
    source_file_path: str
    staging_video_path: str | None = None
    staging_nfo_path: str | None = None
    staging_cover_path: str | None = None
    target_video_path: str | None = None
    target_nfo_path: str | None = None
    target_cover_path: str | None = None


class TaskCreateRequest(BaseModel):
    """创建任务请求。"""

    series_id: int
    season_number: int
    episode_number: int
    title: str
    source_file_path: str
    cover_url: str | None = None
    nfo_json: dict[str, Any] | None = None


class TaskResponse(BaseModel):
    """任务响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: TaskStatus
    series_id: int | None
    series_name: str | None
    emby_series_id: str | None
    library_id: int | None
    library_name: str | None
    season_number: int
    episode_number: int
    title: str | None
    source_file_path: str | None
    staging_video_path: str | None
    staging_nfo_path: str | None
    staging_cover_path: str | None
    target_video_path: str | None
    target_nfo_path: str | None
    target_cover_path: str | None
    nfo_json: dict[str, Any] | None
    error_message: str | None
    committed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class NFOUpdateRequest(BaseModel):
    """NFO 更新请求。"""

    nfo_json: dict[str, Any]


class CoverDownloadRequest(BaseModel):
    """封面下载请求。"""

    cover_url: str
