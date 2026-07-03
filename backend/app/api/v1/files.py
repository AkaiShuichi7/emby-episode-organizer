"""文件浏览与校验 API。"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import get_settings_service
from app.api.v1 import api_v1_router
from app.config import settings as app_settings
from app.services.files import NotAVideoError, browse_directory, validate_source_file
from app.services.settings import SettingsService
from app.utils.path_security import PathSecurityError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["files"])


class PathRequest(BaseModel):
    """单路径请求体。"""

    path: str


async def _resolve_allowed_roots(service: SettingsService) -> list[Path]:
    """从 settings 读取允许浏览根目录，缺失时回退到环境变量。"""

    raw = await service.get("file.allowed_browse_roots")
    if isinstance(raw, list) and raw:
        return [Path(str(item)) for item in raw]

    env_value = getattr(app_settings, "allowed_browse_roots", None)
    if isinstance(env_value, list) and env_value:
        return [Path(str(item)) for item in env_value]

    return []


def _bad_request(detail: str) -> HTTPException:
    """统一构造 400。"""

    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


@router.post("/browse")
async def browse_files(
    body: PathRequest,
    service: SettingsService = Depends(get_settings_service),
) -> dict[str, object]:
    """浏览目录。

    空路径时回退到第一个允许根目录，方便前端首次打开对话框。
    """

    allowed_roots = await _resolve_allowed_roots(service)
    target_path = body.path.strip() if body.path else ""
    if not target_path and allowed_roots:
        target_path = str(allowed_roots[0])
    try:
        result = browse_directory(target_path, allowed_roots)
    except PathSecurityError as exc:
        raise _bad_request(f"浏览路径越界: {exc}") from exc
    except FileNotFoundError as exc:
        raise _bad_request(str(exc)) from exc
    logger.info("浏览目录成功: path=%s entries=%d", result.current_path, len(result.entries))
    return result.model_dump(mode="json")


@router.post("/validate")
async def validate_file(
    body: PathRequest,
    service: SettingsService = Depends(get_settings_service),
) -> dict[str, object]:
    """校验源视频文件。"""

    allowed_roots = await _resolve_allowed_roots(service)
    try:
        result = validate_source_file(body.path, allowed_roots)
    except (PathSecurityError, FileNotFoundError, NotAVideoError) as exc:
        raise _bad_request(str(exc)) from exc
    logger.info("校验源文件成功: path=%s", result.path)
    return result.model_dump(mode="json")


api_v1_router.include_router(router)
