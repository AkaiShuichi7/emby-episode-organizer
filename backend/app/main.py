"""Emby Episode Organizer 后端 FastAPI 应用入口。"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request

from app.api.deps import get_settings_service
# 导入各 v1 子模块以触发模块底部的自挂载（include_router）
from app.api.v1 import settings as _v1_settings  # noqa: F401
from app.api.v1 import emby as _v1_emby  # noqa: F401
from app.api.v1 import libraries as _v1_libraries  # noqa: F401
from app.api.v1 import series as _v1_series  # noqa: F401
from app.api.v1 import tasks as _v1_tasks  # noqa: F401
from app.api.v1 import files as _v1_files  # noqa: F401
from app.api.v1 import api_v1_router
from app.config import settings
from app.db.init_db import init_db
from app.logging_config import setup_logging
from app.services.settings import SettingsService

_ = (_v1_settings, _v1_emby, _v1_libraries, _v1_series, _v1_tasks, _v1_files)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期钩子：启动时初始化数据库表。"""
    setup_logging(settings.log_dir)
    logger.info("应用启动")
    await init_db()
    logger.info("数据库初始化完成")
    yield


app = FastAPI(title="Emby Episode Organizer", version="0.1.0", lifespan=lifespan)


# 挂载 v1 总路由（子模块在 import 时自挂载）
app.include_router(api_v1_router)


@app.get("/health")
async def health(
    service: Annotated[SettingsService, Depends(get_settings_service)],
) -> dict[str, bool | str]:
    """健康检查端点。

    返回三项状态：
    - ``status``: 进程级存活标志，固定 ``ok``。
    - ``db_ok``: settings DB 是否可达，异常时降级为 ``False``。
    - ``emby_configured``: Emby server_url / api_key / auto_refresh 三件套
      是否齐全，缺失则 ``False``。

    DB 不可达时仍返回 200，避免监控把数据库抖动误判成进程级宕机。
    """
    db_ok = True
    emby_configured = False
    try:
        cfg = await service.get_emby_config()
        emby_configured = cfg is not None
    except Exception:
        # 兜底：DB 不可达时仍返回 ok + db_ok=false，让上层有信号区分
        logger.exception("健康检查读取配置失败，降级返回")
        db_ok = False
        emby_configured = False
    return {
        "status": "ok",
        "db_ok": db_ok,
        "emby_configured": emby_configured,
    }


dist_dir = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if dist_dir.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="frontend")
    logger.info("已挂载前端静态文件: %s", dist_dir)
else:
    logger.warning("前端构建产物 %s 未找到，跳过静态文件挂载", dist_dir)


@app.exception_handler(StarletteHTTPException)
async def spa_or_api_not_found(request: Request, exc: StarletteHTTPException) -> JSONResponse | FileResponse:
    """SPA fallback：非 API/health 的 404 返回 index.html，否则原样 JSON。"""
    if exc.status_code == 404 and not request.url.path.startswith(("/api", "/health")):
        index_file = dist_dir / "index.html"
        if index_file.is_file():
            return FileResponse(str(index_file), media_type="text/html")
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
