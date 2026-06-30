"""剧集 (Series) CRUD API。

提供 ``GET / POST / PUT / DELETE /api/v1/series`` 端点：

- 列表支持 ``?library_id=`` 过滤；详情只读；
- 创建 / 更新前会校验 ``library_id`` 是否存在，并对 ``staging_path`` /
  ``target_path`` 调用 :func:`app.utils.path_security.safe_resolve` 校验是否
  落在关联 library 的 ``staging_root`` / ``target_root`` 下，失败返回 400；
- 删除不做级联，关联 tasks 由后续任务显式处理；
- 资源不存在抛 404。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.v1 import api_v1_router
from app.db.models import Library, Series
from app.schemas.series import (
    SeriesCreate,
    SeriesResponse,
    SeriesUpdate,
)
from app.utils.path_security import PathSecurityError, safe_resolve

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/series", tags=["series"])
"""剧集路由，前缀 ``/series``，挂载到 v1 总路由后实际路径为 ``/api/v1/series``。"""


def _ensure_path_inside(path: str, root: str | None, field_name: str) -> None:
    """校验 ``path`` 落在 ``root`` 下，越界抛 400。

    参数:
        path: 待校验的原始路径字符串。
        root: library 的 staging_root / target_root；为空时直接拒绝。
        field_name: 出错时报告的字段名（如 ``staging_path``）。

    抛出:
        HTTPException: 400 + 字段级错误描述。
    """

    if not root:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} 路径校验失败：library 未配置对应根目录",
        )
    try:
        safe_resolve(path, [Path(root)])
    except PathSecurityError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} 不在 library 根目录内: {exc}",
        ) from exc


async def _validate_series_fields(
    db: AsyncSession,
    library_id: int | None,
    staging_path: str | None,
    target_path: str | None,
) -> Library | None:
    """校验 library_id 存在 + 路径落在 library 根目录内。

    规则：
    - 传了路径但未关联 library → 400（没有参照无法校验路径安全）；
    - library_id 不为空但 DB 查不到 → 400；
    - 路径不为空时，调用 ``safe_resolve`` 校验是否落在 library 对应根下。

    参数:
        db: 数据库会话。
        library_id: 请求体中的 library_id。
        staging_path: 请求体中的 staging_path。
        target_path: 请求体中的 target_path。

    返回:
        关联的 ``Library`` 对象；未关联时返回 ``None``。

    抛出:
        HTTPException: 校验失败时返回 400。
    """

    if library_id is None:
        if staging_path or target_path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="staging_path/target_path 需要关联 library 才能校验",
            )
        return None

    library = await db.get(Library, library_id)
    if library is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"library_id={library_id} 不存在",
        )
    if staging_path:
        _ensure_path_inside(staging_path, library.staging_root, "staging_path")
    if target_path:
        _ensure_path_inside(target_path, library.target_root, "target_path")
    return library


def _serialize(series: Series) -> SeriesResponse:
    """把 ORM ``Series`` 序列化为 ``SeriesResponse``。"""

    return SeriesResponse.model_validate(series)


@router.get("", response_model=list[SeriesResponse])
async def list_series(
    library_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[SeriesResponse]:
    """列出全部剧集，可选按 ``library_id`` 过滤。

    参数:
        library_id: 可选过滤参数；为空时返回全部。
        db: 数据库会话。

    返回:
        按主键升序的 series 列表。
    """

    stmt = select(Series).order_by(Series.id)
    if library_id is not None:
        stmt = stmt.where(Series.library_id == library_id)
    result = await db.execute(stmt)
    items = result.scalars().all()
    logger.info("列出剧集 %d 项 (library_id=%s)", len(items), library_id)
    return [_serialize(item) for item in items]


@router.post("", response_model=SeriesResponse, status_code=status.HTTP_201_CREATED)
async def create_series(
    body: SeriesCreate,
    db: AsyncSession = Depends(get_db),
) -> SeriesResponse:
    """创建剧集。

    参数:
        body: 创建请求载荷。
        db: 数据库会话。

    返回:
        新建剧集响应载荷。

    抛出:
        HTTPException: library 不存在或路径越界时返回 400。
    """

    library = await _validate_series_fields(
        db, body.library_id, body.staging_path, body.target_path
    )

    series = Series(
        name=body.name,
        emby_series_id=body.emby_series_id,
        library_id=body.library_id,
        library_name=library.name if library else None,
        staging_path=body.staging_path,
        target_path=body.target_path,
        default_season=body.default_season,
        enabled=body.enabled,
    )
    db.add(series)
    await db.commit()
    await db.refresh(series)
    logger.info(
        "创建剧集: id=%s name=%s library_id=%s",
        series.id, series.name, series.library_id,
    )
    return _serialize(series)


@router.get("/{series_id}", response_model=SeriesResponse)
async def get_series(
    series_id: int,
    db: AsyncSession = Depends(get_db),
) -> SeriesResponse:
    """读取单个剧集详情。

    参数:
        series_id: 剧集主键。
        db: 数据库会话。

    返回:
        剧集响应载荷。

    抛出:
        HTTPException: 不存在时返回 404。
    """

    series = await db.get(Series, series_id)
    if series is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"剧集 {series_id} 不存在",
        )
    return _serialize(series)


@router.put("/{series_id}", response_model=SeriesResponse)
async def update_series(
    series_id: int,
    body: SeriesUpdate,
    db: AsyncSession = Depends(get_db),
) -> SeriesResponse:
    """更新剧集。

    只把请求体中显式传入的字段写到 ORM 对象上；任一路径字段被覆盖时，用
    effective library_id（请求体未传则取 series 当前值）做 ``safe_resolve``
    校验，失败抛 400。

    参数:
        series_id: 待更新的剧集主键。
        body: 更新请求载荷。
        db: 数据库会话。

    返回:
        更新后的剧集响应载荷。

    抛出:
        HTTPException: 不存在 404；library / 路径越界 400。
    """

    series = await db.get(Series, series_id)
    if series is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"剧集 {series_id} 不存在",
        )

    updates: dict[str, Any] = dict(body.model_dump(exclude_unset=True))

    if "staging_path" in updates or "target_path" in updates:
        effective_library_id = updates.get("library_id", series.library_id)
        await _validate_series_fields(
            db,
            effective_library_id,
            updates.get("staging_path"),
            updates.get("target_path"),
        )

    # 同步 library_name：library_id 被显式改动时重新读取名字
    if "library_id" in updates:
        new_lib_id = updates["library_id"]
        if new_lib_id is None:
            updates["library_name"] = None
        else:
            lib = await db.get(Library, new_lib_id)
            if lib is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"library_id={new_lib_id} 不存在",
                )
            updates["library_name"] = lib.name

    for field, value in updates.items():
        setattr(series, field, value)
    await db.commit()
    await db.refresh(series)
    logger.info("更新剧集: id=%s fields=%s", series.id, sorted(updates.keys()))
    return _serialize(series)


@router.delete("/{series_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_series(
    series_id: int,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """删除剧集。

    不做级联删除关联 tasks（由后续任务处理）；id 不存在时返回 404。

    参数:
        series_id: 待删除的剧集主键。
        db: 数据库会话。

    返回:
        204 No Content。

    抛出:
        HTTPException: 不存在时返回 404。
    """

    series = await db.get(Series, series_id)
    if series is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"剧集 {series_id} 不存在",
        )
    await db.delete(series)
    await db.commit()
    logger.info("删除剧集: id=%s name=%s", series_id, series.name)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# 模块加载时自动挂载到 v1 总路由
api_v1_router.include_router(router)
