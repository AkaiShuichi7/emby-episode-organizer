"""Emby Episode Organizer 后端 FastAPI 应用入口。"""

from fastapi import FastAPI

app = FastAPI(title="Emby Episode Organizer", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    """健康检查端点。"""
    return {"status": "ok"}
