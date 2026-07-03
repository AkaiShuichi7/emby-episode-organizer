"""任务 API。"""

from __future__ import annotations

import logging
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Any, NamedTuple

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_settings_service
from app.api.v1 import api_v1_router
from app.config import settings as app_settings
from app.db import SessionLocal
from app.db.models import Series, Task, TaskStatus
from app.schemas.task import (
    CoverDownloadRequest,
    NFOUpdateRequest,
    TaskCreateRequest,
    TaskPreviewRequest,
    TaskPreviewResponse,
    TaskResponse,
)
from app.services.cover import ALLOWED_CONTENT_TYPES, MAX_COVER_SIZE, download_cover
from app.services.files import validate_source_file
from app.services.mover import FileConflictError, commit_to_target
from app.services.nfo import NFOData, build_nfo_xml
from app.services.settings import SettingsService
from app.utils.naming import (
    NamingContext,
    generate_nfo_filename,
    generate_season_folder,
    generate_thumb_filename,
    generate_video_filename,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskPaths(NamedTuple):
    """任务文件路径集合。"""

    staging_video_path: str | None
    staging_nfo_path: str | None
    staging_cover_path: str | None
    target_video_path: str | None
    target_nfo_path: str | None
    target_cover_path: str | None


async def _resolve_allowed_roots(service: SettingsService) -> list[Path]:
    """从 settings 读取允许浏览根目录，缺失时回退到环境变量 ``ALLOWED_BROWSE_ROOTS``。

    优先级：DB → 环境变量（含默认值 ``['/data']``）。
    """

    raw = await service.get("file.allowed_browse_roots")
    if isinstance(raw, list) and raw:
        return [Path(str(item)) for item in raw]
    env_value = getattr(app_settings, "allowed_browse_roots", None)
    if isinstance(env_value, list) and env_value:
        return [Path(str(item)) for item in env_value]
    return []


async def _get_series_or_404(db: AsyncSession, series_id: int) -> Series:
    """读取 series，不存在抛 404。"""

    series = await db.get(Series, series_id)
    if series is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"剧集 {series_id} 不存在",
        )
    return series


def _serialize(task: Task) -> TaskResponse:
    """序列化任务。"""

    return TaskResponse.model_validate(task)


def _ensure_series_paths(series: Series) -> tuple[Path, Path]:
    """确认 series 已配置 staging/target 路径。"""

    if not series.staging_path or not series.target_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="series 未配置 staging_path 或 target_path",
        )
    return Path(series.staging_path), Path(series.target_path)


def _build_paths(
    series: Series,
    season_number: int,
    episode_number: int | None,
    title: str,
    source_ext: str,
) -> TaskPaths:
    """按命名规则计算 staging/target 路径。"""

    if episode_number is None:
        return TaskPaths(None, None, None, None, None, None)

    staging_root, target_root = _ensure_series_paths(series)
    ctx = NamingContext(
        series=series.name,
        season=season_number,
        episode=episode_number,
        title=title,
        ext=source_ext,
    )
    video_name = generate_video_filename(ctx)
    nfo_name = generate_nfo_filename(ctx)
    thumb_name = generate_thumb_filename(ctx)
    season_dir = generate_season_folder(season_number)
    return TaskPaths(
        staging_video_path=str(staging_root / video_name),
        staging_nfo_path=str(staging_root / nfo_name),
        staging_cover_path=str(staging_root / thumb_name),
        target_video_path=str(target_root / season_dir / video_name),
        target_nfo_path=str(target_root / season_dir / nfo_name),
        target_cover_path=str(target_root / season_dir / thumb_name),
    )


def _build_nfo_payload(task: Task, raw_nfo_json: dict[str, Any]) -> NFOData:
    """把字典校验为 NFOData，字符串类型的多值字段自动归一为列表。"""

    # 字符串类型的多值字段："" → []，非空 → [value]
    list_fields = ("genre", "tag", "director")
    normalized: dict[str, Any] = dict(raw_nfo_json)
    for field in list_fields:
        value = normalized.get(field)
        if isinstance(value, str):
            normalized[field] = [value] if value.strip() else []

    merged = {
        "title": task.title or "",
        "season": task.season_number,
        "episode": task.episode_number,
        **normalized,
    }
    return NFOData.model_validate(merged)


def _write_nfo_file(path: str, data: NFOData) -> None:
    """写 staging NFO 文件。"""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build_nfo_xml(data), encoding="utf-8")


def _collect_staging_files(task: Task) -> list[Path]:
    """收集存在的 staging 文件。"""

    values = [task.staging_video_path, task.staging_nfo_path, task.staging_cover_path]
    files = [Path(item) for item in values if item]
    return [path for path in files if path.exists()]


def _cleanup_task_staging(task: Task) -> None:
    """删除任务对应的 staging 文件。"""

    removed = 0
    for field in (task.staging_video_path, task.staging_nfo_path, task.staging_cover_path):
        if field is None:
            continue
        path = Path(field)
        try:
            path.unlink(missing_ok=True)
            removed += 1
        except OSError as exc:
            logger.warning("删除 staging 文件失败: path=%s err=%s", path, exc)
    if removed:
        logger.info("清理 staging 文件: task_id=%s count=%d", task.id, removed)


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    status_filter: TaskStatus | None = Query(default=None, alias="status"),
    series_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[TaskResponse]:
    """列出任务，支持状态与剧集过滤。"""

    stmt = select(Task).order_by(Task.id)
    if status_filter is not None:
        stmt = stmt.where(Task.status == status_filter)
    if series_id is not None:
        stmt = stmt.where(Task.series_id == series_id)
    result = await db.execute(stmt)
    items = result.scalars().all()
    logger.info("列出任务 %d 项", len(items))
    return [_serialize(item) for item in items]


@router.post("/preview", response_model=TaskPreviewResponse)
async def preview_task(
    body: TaskPreviewRequest,
    db: AsyncSession = Depends(get_db),
    service: SettingsService = Depends(get_settings_service),
) -> TaskPreviewResponse:
    """预览任务路径，不入库。"""

    series = await _get_series_or_404(db, body.series_id)
    allowed_roots = await _resolve_allowed_roots(service)
    source_info = validate_source_file(body.source_file_path, allowed_roots)
    paths = _build_paths(
        series,
        body.season_number,
        body.episode_number,
        body.title,
        source_info.extension,
    )
    logger.info("预览任务路径成功: series_id=%s episode=%s", body.series_id, body.episode_number)
    return TaskPreviewResponse(
        series_id=body.series_id,
        season_number=body.season_number,
        episode_number=body.episode_number,
        title=body.title,
        source_file_path=body.source_file_path,
        **paths._asdict(),
    )


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    body: TaskCreateRequest,
    db: AsyncSession = Depends(get_db),
    service: SettingsService = Depends(get_settings_service),
) -> TaskResponse:
    """创建任务。"""

    series = await _get_series_or_404(db, body.series_id)
    allowed_roots = await _resolve_allowed_roots(service)
    source_info = validate_source_file(body.source_file_path, allowed_roots)
    paths = _build_paths(
        series,
        body.season_number,
        body.episode_number,
        body.title,
        source_info.extension,
    )

    task = Task(
        status=TaskStatus.DRAFT,
        series_id=series.id,
        series_name=series.name,
        emby_series_id=series.emby_series_id,
        library_id=series.library_id,
        library_name=series.library_name,
        season_number=body.season_number,
        episode_number=body.episode_number,
        title=body.title,
        source_file_path=str(source_info.path),
        staging_video_path=paths.staging_video_path,
        staging_nfo_path=paths.staging_nfo_path,
        staging_cover_path=paths.staging_cover_path,
        target_video_path=paths.target_video_path,
        target_nfo_path=paths.target_nfo_path,
        target_cover_path=paths.target_cover_path,
        nfo_json=body.nfo_json,
    )

    try:
        if body.nfo_json is not None:
            nfo_data = _build_nfo_payload(task, body.nfo_json)
            if task.staging_nfo_path is not None:
                _write_nfo_file(task.staging_nfo_path, nfo_data)
            task.status = TaskStatus.STAGED
        if task.staging_video_path is not None:
            target = Path(task.staging_video_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(Path(source_info.path).read_bytes())
            if body.nfo_json is not None:
                task.status = TaskStatus.STAGED
        if body.cover_url and task.staging_cover_path is not None:
            cover_target = Path(task.staging_cover_path)
            cover_target.parent.mkdir(parents=True, exist_ok=True)
            await download_cover(body.cover_url, cover_target)
            task.status = TaskStatus.STAGED
        db.add(task)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="同一剧集/季/集任务已存在",
        ) from exc
    except HTTPException:
        await db.rollback()
        raise
    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"创建任务失败: {exc}",
        ) from exc

    await db.refresh(task)
    logger.info("创建任务成功: id=%s status=%s", task.id, task.status)
    return _serialize(task)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)) -> TaskResponse:
    """读取任务详情。"""

    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"任务 {task_id} 不存在")
    return _serialize(task)


@router.put("/{task_id}/nfo", response_model=TaskResponse)
async def update_task_nfo(
    task_id: int,
    body: NFOUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """更新任务 NFO，并重写 staging NFO 文件。"""

    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"任务 {task_id} 不存在")
    editable_statuses = {
        TaskStatus.DRAFT,
        TaskStatus.STAGED,
        TaskStatus.NFO_EDITED,
        TaskStatus.FAILED,
    }
    if task.status not in editable_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"当前状态 {task.status.value} 不允许编辑 NFO",
        )
    if task.staging_nfo_path is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务未配置 staging NFO 路径")

    nfo_data = _build_nfo_payload(task, body.nfo_json)
    _write_nfo_file(task.staging_nfo_path, nfo_data)
    task.nfo_json = body.nfo_json
    if task.status == TaskStatus.DRAFT:
        task.status = TaskStatus.STAGED
    await db.commit()
    await db.refresh(task)
    logger.info("更新任务 NFO 成功: id=%s", task.id)
    return _serialize(task)


@router.post("/{task_id}/cover/upload", response_model=TaskResponse)
async def upload_task_cover(
    task_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """上传封面到 staging。"""

    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"任务 {task_id} 不存在")
    if task.staging_cover_path is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务未配置 staging 封面路径")

    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="封面 content-type 不支持")

    target = Path(task.staging_cover_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    if len(content) > MAX_COVER_SIZE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="封面上传超过 20MB 限制")
    target.write_bytes(content)
    if task.status == TaskStatus.DRAFT:
        task.status = TaskStatus.STAGED
    await db.commit()
    await db.refresh(task)
    logger.info("上传任务封面成功: id=%s path=%s", task.id, target)
    return _serialize(task)


@router.post("/{task_id}/cover/download", response_model=TaskResponse)
async def download_task_cover(
    task_id: int,
    body: CoverDownloadRequest,
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """下载封面到 staging。"""

    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"任务 {task_id} 不存在")
    if task.staging_cover_path is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务未配置 staging 封面路径")

    target = Path(task.staging_cover_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    await download_cover(body.cover_url, target)
    if task.status == TaskStatus.DRAFT:
        task.status = TaskStatus.STAGED
    await db.commit()
    await db.refresh(task)
    logger.info("下载任务封面成功: id=%s path=%s", task.id, target)
    return _serialize(task)


@router.get("/{task_id}/cover/raw")
async def get_task_cover_raw(task_id: int, db: AsyncSession = Depends(get_db)) -> FileResponse:
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"任务 {task_id} 不存在")

    cover_path = task.staging_cover_path or task.target_cover_path
    if not cover_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务未配置封面路径")

    path = Path(cover_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="封面文件不存在")

    media_type, _ = mimetypes.guess_type(str(path))
    if not media_type:
        media_type = "application/octet-stream"
    return FileResponse(path, media_type=media_type)


async def _commit_background(task_id: int, staging_files: list[Path], target_dir: Path) -> None:
    """后台执行任务提交。"""

    async with SessionLocal() as db:
        task = await db.get(Task, task_id)
        if task is None:
            logger.error("后台提交失败: 任务 %d 不存在", task_id)
            return

        try:
            await commit_to_target(staging_files, target_dir)
            task.status = TaskStatus.COMMITTED
            task.error_message = None
            task.committed_at = datetime.now()
            logger.info("后台提交任务成功: id=%s", task.id)
        except FileConflictError as exc:
            task.status = TaskStatus.FAILED
            task.error_message = str(exc)
            logger.warning("后台提交任务冲突: id=%s err=%s", task.id, exc)
        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error_message = str(exc)
            logger.error("后台提交任务异常: id=%s err=%s", task.id, exc)

        await db.commit()


@router.post("/{task_id}/commit", response_model=TaskResponse)
async def commit_task(
    task_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """提交任务到目标目录（异步）。"""

    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"任务 {task_id} 不存在")
    if task.status == TaskStatus.COMMITTED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务已提交")
    if task.target_video_path is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务未配置目标视频路径")

    staging_files = _collect_staging_files(task)
    background_tasks.add_task(
        _commit_background,
        task.id,
        staging_files,
        Path(task.target_video_path).parent,
    )

    logger.info("已触发后台提交任务: id=%s", task.id)
    return _serialize(task)


@router.post("/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(task_id: int, db: AsyncSession = Depends(get_db)) -> TaskResponse:
    """取消未入库任务，并清理对应的 staging 文件。"""

    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"任务 {task_id} 不存在")

    cancellable = {
        TaskStatus.DRAFT,
        TaskStatus.STAGED,
        TaskStatus.NFO_EDITED,
        TaskStatus.FAILED,
    }
    if task.status not in cancellable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"当前状态 {task.status.value} 不允许取消",
        )

    _cleanup_task_staging(task)
    task.status = TaskStatus.CANCELLED
    await db.commit()
    await db.refresh(task)
    logger.info("取消任务成功: id=%s", task_id)
    return _serialize(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: int, db: AsyncSession = Depends(get_db)) -> Response:
    """删除任务记录，仅删 DB 记录，staging 文件（如有）一并清理。"""

    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"任务 {task_id} 不存在")

    _cleanup_task_staging(task)
    await db.delete(task)
    await db.commit()
    logger.info("删除任务成功: id=%s status=%s", task_id, task.status.value)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


api_v1_router.include_router(router)
