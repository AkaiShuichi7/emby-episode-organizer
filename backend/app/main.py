"""Emby Episode Organizer 后端 FastAPI 应用入口。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db.init_db import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期钩子：启动时初始化数据库表。"""
    await init_db()
    yield


app = FastAPI(title="Emby Episode Organizer", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    """健康检查端点。"""
    return {"status": "ok"}
