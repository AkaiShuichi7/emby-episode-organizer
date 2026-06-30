"""健康检查测试。"""

from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_health() -> None:
    """健康检查端点返回 ok。"""
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
