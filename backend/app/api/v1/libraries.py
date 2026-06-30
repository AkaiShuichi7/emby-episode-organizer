"""媒体库 (Library) CRUD API。

提供 ``GET / POST / PUT / DELETE /api/v1/libraries`` 等端点：

- 列表与详情只读；
- 创建 / 更新前会调用 :func:`app.utils.path_security.safe_resolve` 校验
  ``staging_root`` 与 ``target_root`` 是否落在 ``file.allowed_browse_roots``
  允许根目录内，失败返回 400；
- 删除不做级联，关联 series 由后续任务显式处理；
- 鉴权 / 业务级异常统一由 FastAPI 默认异常处理；端点路径越界时手工抛
  HTTPException 400，资源不存在抛 404。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_settings_service
from app.api.v1 import api_v1_router
from app.db.models import Library
from app.schemas.library import (
    LibraryCreate,
    LibraryResponse,
    LibraryUpdate,
)
from app.services.settings import SettingsService
from app.utils.path_security import PathSecurityError, safe_resolve

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/libraries", tags=["libraries"])
"""媒体库路由，前缀 ``/libraries``，挂载到 v1 总路由后实际路径为 ``/api/v1/libraries``。"""


async def _resolve_allowed_roots(service: SettingsService) -> list[Path]:
    """从 settings 服务读取 ``file.allowed_browse_roots`` 并解析为 ``Path`` 列表。

    参数:
        service: 注入的设置服务实例。

    返回:
        允许根目录列表；DB 中缺值或为空列表时返回空列表（空列表会让所有路径校验
        失败，是预期的"未配置"语义）。
    """

    raw = await service.get("file.allowed_browse_roots")
    if not raw:
        return []
    if not isinstance(raw, list):
        return []
    return [Path(str(item)) for item in raw]


def _ensure_path_allowed(path: str, field_name: str, allowed_roots: list[Path]) -> None:
    """调用 :func:`safe_resolve` 校验单条路径，越界抛 400。

    参数:
        path: 待校验的原始路径字符串。
        field_name: 出错时报告的字段名（如 ``staging_root``），便于前端定位。
        allowed_roots: 允许根目录列表；为空时所有路径都会被拒绝。

    抛出:
        HTTPException: 400 + 字段级错误描述。
    """

    if not allowed_roots:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} 路径校验失败：未配置允许的根目录",
        )
    try:
        safe_resolve(path, allowed_roots)
    except PathSecurityError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} 路径不在允许的根目录内: {exc}",
        ) from exc


def _serialize(library: Library) -> LibraryResponse:
    """把 ORM ``Library`` 序列化为 ``LibraryResponse``。"""

    return LibraryResponse.model_validate(library)


@router.get("", response_model=list[LibraryResponse])
async def list_libraries(
    db: AsyncSession = Depends(get_db),
) -> list[LibraryResponse]:
    """列出全部媒体库。

    返回:
        按主键升序的所有媒体库。
    """

    result = await db.execute(select(Library).order_by(Library.id))
    libraries = result.scalars().all()
    logger.info("列出媒体库 %d 项", len(libraries))
    return [_serialize(item) for item in libraries]


@router.post("", response_model=LibraryResponse, status_code=status.HTTP_201_CREATED)
async def create_library(
    body: LibraryCreate,
    db: AsyncSession = Depends(get_db),
    service: SettingsService = Depends(get_settings_service),
) -> LibraryResponse:
    """创建媒体库。

    参数:
        body: 创建请求载荷，``name`` / ``staging_root`` / ``target_root`` 必填。
        db: 与 ``service`` 共享的 session，用于 commit。
        service: 注入的设置服务，用于读取 ``file.allowed_browse_roots``。

    返回:
        新建媒体库的响应载荷。

    抛出:
        HTTPException: 路径越界时返回 400。
    """

    allowed_roots = await _resolve_allowed_roots(service)
    _ensure_path_allowed(body.staging_root, "staging_root", allowed_roots)
    _ensure_path_allowed(body.target_root, "target_root", allowed_roots)

    library = Library(
        name=body.name,
        collection_type=body.collection_type,
        staging_root=body.staging_root,
        target_root=body.target_root,
        enabled=body.enabled,
    )
    db.add(library)
    await db.commit()
    await db.refresh(library)
    logger.info(
        "创建媒体库: id=%s name=%s", library.id, library.name,
    )
    return _serialize(library)


@router.get("/{library_id}", response_model=LibraryResponse)
async def get_library(
    library_id: int,
    db: AsyncSession = Depends(get_db),
) -> LibraryResponse:
    """读取单个媒体库详情。

    参数:
        library_id: 媒体库主键。
        db: 数据库会话。

    返回:
        媒体库响应载荷。

    抛出:
        HTTPException: 不存在时返回 404。
    """

    library = await db.get(Library, library_id)
    if library is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"媒体库 {library_id} 不存在",
        )
    return _serialize(library)


@router.put("/{library_id}", response_model=LibraryResponse)
async def update_library(
    library_id: int,
    body: LibraryUpdate,
    db: AsyncSession = Depends(get_db),
    service: SettingsService = Depends(get_settings_service),
) -> LibraryResponse:
    """更新媒体库。

    只把请求体中非空的字段写到 ORM 对象上；任一路径字段被覆盖时先做
    ``safe_resolve`` 校验，校验失败抛 400 且不改 DB。

    参数:
        library_id: 待更新的媒体库主键。
        body: 更新请求载荷，字段全部可选。
        db: 数据库会话。
        service: 注入的设置服务，用于读取 ``file.allowed_browse_roots``。

    返回:
        更新后的媒体库响应载荷。

    抛出:
        HTTPException: 不存在 404；路径越界 400。
    """

    library = await db.get(Library, library_id)
    if library is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"媒体库 {library_id} 不存在",
        )

    updates: dict[str, Any] = dict(body.model_dump(exclude_unset=True))
    if "staging_root" in updates:
        allowed_roots = await _resolve_allowed_roots(service)
        _ensure_path_allowed(updates["staging_root"], "staging_root", allowed_roots)
    if "target_root" in updates:
        allowed_roots = await _resolve_allowed_roots(service)
        _ensure_path_allowed(updates["target_root"], "target_root", allowed_roots)

    for field, value in updates.items():
        setattr(library, field, value)
    await db.commit()
    await db.refresh(library)
    logger.info("更新媒体库: id=%s fields=%s", library.id, sorted(updates.keys()))
    return _serialize(library)


@router.delete("/{library_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_library(
    library_id: int,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """删除媒体库。

    不做级联删除关联 series（由后续任务处理）；id 不存在时返回 404。

    参数:
        library_id: 待删除的媒体库主键。
        db: 数据库会话。

    返回:
        204 No Content。

    抛出:
        HTTPException: 不存在时返回 404。
    """

    library = await db.get(Library, library_id)
    if library is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"媒体库 {library_id} 不存在",
        )
    await db.delete(library)
    await db.commit()
    logger.info("删除媒体库: id=%s name=%s", library_id, library.name)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# 模块加载时自动挂载到 v1 总路由
api_v1_router.include_router(router)
