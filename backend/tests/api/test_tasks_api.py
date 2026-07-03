"""Tasks API 端到端测试。

覆盖预览、创建、详情、NFO 更新、封面下载、提交、删除与冲突分支。
"""

from __future__ import annotations

import asyncio
import io
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, cast

import pytest
import respx
from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import app.api.v1.tasks as tasks_module
from app.api.deps import get_db
from app.db import Base
from app.db.models import Setting, Task, TaskStatus
from app.main import app
from app.services.settings import init_default_settings
from app.utils.naming import (
    NamingContext,
    generate_nfo_filename,
    generate_season_folder,
    generate_thumb_filename,
    generate_video_filename,
)


def _make_jpeg_bytes(width: int = 8, height: int = 8) -> bytes:
    """生成有效 JPEG 字节。"""

    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(255, 0, 0)).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
async def test_engine() -> AsyncIterator[AsyncEngine]:
    """提供内存 SQLite 异步引擎并建表。"""

    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
async def client(
    tmp_path, test_engine: AsyncEngine
) -> AsyncIterator[AsyncClient]:
    """覆盖 ``get_db`` 到 in-memory，并把浏览根目录设为 ``tmp_path``。"""

    maker = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    original_session_local = tasks_module.SessionLocal
    tasks_module.SessionLocal = maker
    allowed_roots = [str(tmp_path)]

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with maker() as session:
            await init_default_settings(session)
            result = await session.execute(
                select(Setting).where(Setting.key == "file.allowed_browse_roots").limit(1)
            )
            row = result.scalar_one_or_none()
            if row is not None:
                row.value = cast(Any, allowed_roots)
            else:
                session.add(Setting(key="file.allowed_browse_roots", value=allowed_roots))
            await session.commit()
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    tasks_module.SessionLocal = original_session_local


async def _create_library(client: AsyncClient, tmp_path: Path) -> dict[str, Any]:
    """辅助：创建 library。"""

    response = await client.post(
        "/api/v1/libraries",
        json={
            "name": "动画",
            "staging_root": str(tmp_path / "staging-root"),
            "target_root": str(tmp_path / "target-root"),
        },
    )
    assert response.status_code == 201
    return response.json()


async def _create_series(client: AsyncClient, tmp_path: Path) -> dict[str, Any]:
    """辅助：创建带 staging/target 路径的 series。"""

    library = await _create_library(client, tmp_path)
    staging_path = tmp_path / "staging-root" / "银河铁道"
    target_path = tmp_path / "target-root" / "银河铁道"
    response = await client.post(
        "/api/v1/series",
        json={
            "name": "银河铁道",
            "library_id": library["id"],
            "staging_path": str(staging_path),
            "target_path": str(target_path),
            "emby_series_id": "emby-series-1",
        },
    )
    assert response.status_code == 201
    return response.json()


def _paths_payload(series: dict[str, Any], source_path: Path) -> dict[str, Any]:
    """辅助：构造任务请求载荷。"""

    return {
        "series_id": series["id"],
        "season_number": 1,
        "episode_number": 2,
        "title": "启程",
        "source_file_path": str(source_path),
    }


def _expected_paths(series: dict[str, Any], ext: str = ".mkv") -> dict[str, str]:
    """辅助：按命名规则计算期望路径。"""

    ctx = NamingContext(series=series["name"], season=1, episode=2, title="启程", ext=ext)
    video_name = generate_video_filename(ctx)
    nfo_name = generate_nfo_filename(ctx)
    thumb_name = generate_thumb_filename(ctx)
    season_dir = generate_season_folder(1)
    return {
        "staging_video_path": str(Path(series["staging_path"]) / video_name),
        "staging_nfo_path": str(Path(series["staging_path"]) / nfo_name),
        "staging_cover_path": str(Path(series["staging_path"]) / thumb_name),
        "target_video_path": str(Path(series["target_path"]) / season_dir / video_name),
        "target_nfo_path": str(Path(series["target_path"]) / season_dir / nfo_name),
        "target_cover_path": str(Path(series["target_path"]) / season_dir / thumb_name),
    }


def _write_staging_files(paths: dict[str, str]) -> None:
    """辅助：写入 staging 文件。"""

    for key, content in (
        ("staging_video_path", b"video"),
        ("staging_nfo_path", b"<nfo />"),
        ("staging_cover_path", b"cover"),
    ):
        path = Path(paths[key])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


async def test_preview_returns_expected_paths(client: AsyncClient, tmp_path: Path) -> None:
    """``POST /api/v1/tasks/preview`` 返回 staging/target 路径预览。"""

    series = await _create_series(client, tmp_path)
    source = tmp_path / "source" / "episode.mkv"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"video")

    response = await client.post("/api/v1/tasks/preview", json=_paths_payload(series, source))

    assert response.status_code == 200
    body = response.json()
    assert body["series_id"] == series["id"]
    assert body["season_number"] == 1
    assert body["episode_number"] == 2
    assert body["title"] == "启程"
    assert body["source_file_path"] == str(source)
    assert {key: body[key] for key in _expected_paths(series)} == _expected_paths(series)


async def test_create_task_sets_status_staged(client: AsyncClient, tmp_path: Path) -> None:
    """``POST /api/v1/tasks`` 创建后状态为 ``staged``。"""

    series = await _create_series(client, tmp_path)
    source = tmp_path / "source" / "episode.mkv"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"video")

    response = await client.post(
        "/api/v1/tasks",
        json={
            **_paths_payload(series, source),
            "nfo_json": {"title": "启程", "season": 1, "episode": 2, "plot": "出发"},
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == TaskStatus.STAGED.value
    assert Path(body["staging_nfo_path"]).exists()


async def test_create_task_conflict_returns_409(client: AsyncClient, tmp_path: Path) -> None:
    """重复创建同一集任务时返回 409。"""

    series = await _create_series(client, tmp_path)
    source = tmp_path / "source" / "episode.mkv"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"video")

    first = await client.post(
        "/api/v1/tasks",
        json={**_paths_payload(series, source), "nfo_json": {"title": "启程", "season": 1, "episode": 2}},
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/tasks",
        json={**_paths_payload(series, source), "nfo_json": {"title": "启程", "season": 1, "episode": 2}},
    )

    assert second.status_code == 409


async def test_list_tasks_supports_filters(
    client: AsyncClient, tmp_path: Path
) -> None:
    """``GET /api/v1/tasks`` 支持按状态与 series_id 过滤。"""

    series = await _create_series(client, tmp_path)
    source = tmp_path / "source" / "episode.mkv"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"video")
    create_response = await client.post(
        "/api/v1/tasks",
        json={**_paths_payload(series, source), "nfo_json": {"title": "启程", "season": 1, "episode": 2}},
    )
    task_id = create_response.json()["id"]

    response = await client.get(
        f"/api/v1/tasks?status={TaskStatus.STAGED.value}&series_id={series['id']}"
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == task_id


async def test_get_task_returns_detail(client: AsyncClient, tmp_path: Path) -> None:
    """``GET /api/v1/tasks/{id}`` 返回任务详情。"""

    series = await _create_series(client, tmp_path)
    source = tmp_path / "source" / "episode.mkv"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"video")
    create_response = await client.post(
        "/api/v1/tasks",
        json={**_paths_payload(series, source), "nfo_json": {"title": "启程", "season": 1, "episode": 2}},
    )
    task_id = create_response.json()["id"]

    response = await client.get(f"/api/v1/tasks/{task_id}")

    assert response.status_code == 200
    assert response.json()["id"] == task_id


async def test_get_task_returns_404_when_not_found(client: AsyncClient) -> None:
    """不存在任务返回 404。"""

    response = await client.get("/api/v1/tasks/9999")

    assert response.status_code == 404


async def test_update_nfo_writes_staging_nfo_file(client: AsyncClient, tmp_path: Path) -> None:
    """``PUT /api/v1/tasks/{id}/nfo`` 更新后重新写 staging NFO。"""

    series = await _create_series(client, tmp_path)
    source = tmp_path / "source" / "episode.mkv"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"video")
    create_response = await client.post(
        "/api/v1/tasks",
        json={**_paths_payload(series, source), "nfo_json": {"title": "启程", "season": 1, "episode": 2}},
    )
    task = create_response.json()

    response = await client.put(
        f"/api/v1/tasks/{task['id']}/nfo",
        json={"nfo_json": {"title": "新标题", "season": 1, "episode": 2, "plot": "已改"}},
    )

    assert response.status_code == 200
    text = Path(task["staging_nfo_path"]).read_text(encoding="utf-8")
    assert "新标题" in text
    assert "已改" in text


@pytest.mark.parametrize("transition,status_code", [("commit", 400), ("cancel", 400)])
async def test_update_nfo_rejects_committed_and_cancelled_tasks(
    client: AsyncClient,
    tmp_path: Path,
    transition: str,
    status_code: int,
) -> None:
    """已提交与已取消任务不允许更新 NFO。"""

    series = await _create_series(client, tmp_path)
    source = tmp_path / "source" / "episode.mkv"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"video")
    create_response = await client.post(
        "/api/v1/tasks",
        json={**_paths_payload(series, source), "nfo_json": {"title": "启程", "season": 1, "episode": 2}},
    )
    task_id = create_response.json()["id"]

    if transition == "commit":
        transition_response = await client.post(f"/api/v1/tasks/{task_id}/commit")
        assert transition_response.status_code == 200
        await asyncio.sleep(0.1)
    else:
        transition_response = await client.post(f"/api/v1/tasks/{task_id}/cancel")
        assert transition_response.status_code == 200

    response = await client.put(
        f"/api/v1/tasks/{task_id}/nfo",
        json={"nfo_json": {"title": "新标题", "season": 1, "episode": 2}},
    )

    assert response.status_code == status_code


async def test_cover_download_saves_cover_file(client: AsyncClient, tmp_path: Path) -> None:
    """``POST /api/v1/tasks/{id}/cover/download`` 下载封面到 staging。"""

    series = await _create_series(client, tmp_path)
    source = tmp_path / "source" / "episode.mkv"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"video")
    create_response = await client.post(
        "/api/v1/tasks",
        json={**_paths_payload(series, source), "nfo_json": {"title": "启程", "season": 1, "episode": 2}},
    )
    task = create_response.json()
    jpeg = _make_jpeg_bytes()

    with respx.mock(base_url="https://cdn.example.com") as mock:
        route = mock.get("/cover.jpg").respond(
            200,
            content=jpeg,
            headers={"Content-Type": "image/jpeg"},
        )
        response = await client.post(
            f"/api/v1/tasks/{task['id']}/cover/download",
            json={"cover_url": "https://cdn.example.com/cover.jpg"},
        )

    assert route.called
    assert response.status_code == 200
    assert Path(task["staging_cover_path"]).read_bytes() == jpeg


async def test_cover_upload_saves_uploaded_file(client: AsyncClient, tmp_path: Path) -> None:
    """``POST /api/v1/tasks/{id}/cover/upload`` 保存上传封面。"""

    series = await _create_series(client, tmp_path)
    source = tmp_path / "source" / "episode.mkv"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"video")
    create_response = await client.post(
        "/api/v1/tasks",
        json={**_paths_payload(series, source), "nfo_json": {"title": "启程", "season": 1, "episode": 2}},
    )
    task = create_response.json()
    jpeg = _make_jpeg_bytes()

    response = await client.post(
        f"/api/v1/tasks/{task['id']}/cover/upload",
        files={"file": ("cover.jpg", jpeg, "image/jpeg")},
    )

    assert response.status_code == 200
    assert Path(task["staging_cover_path"]).read_bytes() == jpeg


async def test_commit_task_marks_committed(client: AsyncClient, tmp_path: Path) -> None:
    """``POST /api/v1/tasks/{id}/commit`` 成功后状态为 ``committed``。"""

    series = await _create_series(client, tmp_path)
    source = tmp_path / "source" / "episode.mkv"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"video-data")
    create_response = await client.post(
        "/api/v1/tasks",
        json={**_paths_payload(series, source), "nfo_json": {"title": "启程", "season": 1, "episode": 2}},
    )
    task_id = create_response.json()["id"]

    response = await client.post(f"/api/v1/tasks/{task_id}/commit")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] != TaskStatus.COMMITTED.value
    await asyncio.sleep(0.1)
    committed = await client.get(f"/api/v1/tasks/{task_id}")
    committed_body = committed.json()
    assert committed_body["status"] == TaskStatus.COMMITTED.value
    assert Path(committed_body["target_video_path"]).exists()
    assert Path(committed_body["staging_video_path"]).exists() is False


async def test_commit_task_returns_409_when_already_committed(
    client: AsyncClient, tmp_path: Path
) -> None:
    """已提交任务再次提交返回 409。"""

    series = await _create_series(client, tmp_path)
    source = tmp_path / "source" / "episode.mkv"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"video-data")
    create_response = await client.post(
        "/api/v1/tasks",
        json={**_paths_payload(series, source), "nfo_json": {"title": "启程", "season": 1, "episode": 2}},
    )
    task_id = create_response.json()["id"]

    first = await client.post(f"/api/v1/tasks/{task_id}/commit")
    assert first.status_code == 200
    await asyncio.sleep(0.1)
    second = await client.post(f"/api/v1/tasks/{task_id}/commit")

    assert second.status_code == 409


@pytest.mark.parametrize("initial_status", [TaskStatus.DRAFT, TaskStatus.FAILED])
async def test_cancel_direct_task_marks_cancelled(
    client: AsyncClient,
    tmp_path: Path,
    test_engine: AsyncEngine,
    initial_status: TaskStatus,
) -> None:
    """草稿与失败任务允许取消。"""

    series = await _create_series(client, tmp_path)
    expected = _expected_paths(series)
    maker = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        task = Task(
            status=initial_status,
            series_id=series["id"],
            series_name=series["name"],
            emby_series_id=series["emby_series_id"],
            library_id=series["library_id"],
            library_name=series["library_name"],
            season_number=1,
            episode_number=2,
            title="启程",
            source_file_path=str(tmp_path / "source" / "episode.mkv"),
            staging_video_path=expected["staging_video_path"],
            staging_nfo_path=expected["staging_nfo_path"],
            staging_cover_path=expected["staging_cover_path"],
            target_video_path=expected["target_video_path"],
            target_nfo_path=expected["target_nfo_path"],
            target_cover_path=expected["target_cover_path"],
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        task_id = task.id

    response = await client.post(f"/api/v1/tasks/{task_id}/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == TaskStatus.CANCELLED.value


async def test_cancel_staged_task_marks_cancelled(client: AsyncClient, tmp_path: Path) -> None:
    """暂存任务允许取消。"""

    series = await _create_series(client, tmp_path)
    expected = _expected_paths(series)
    _write_staging_files(expected)
    source = tmp_path / "source" / "episode.mkv"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"video-data")
    create_response = await client.post(
        "/api/v1/tasks",
        json={**_paths_payload(series, source), "nfo_json": {"title": "启程", "season": 1, "episode": 2}},
    )
    task_id = create_response.json()["id"]

    response = await client.post(f"/api/v1/tasks/{task_id}/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == TaskStatus.CANCELLED.value
    assert not Path(expected["staging_video_path"]).exists()
    assert not Path(expected["staging_nfo_path"]).exists()
    assert not Path(expected["staging_cover_path"]).exists()


async def test_cancel_committed_task_returns_400(client: AsyncClient, tmp_path: Path) -> None:
    """已提交任务不可取消。"""

    series = await _create_series(client, tmp_path)
    source = tmp_path / "source" / "episode.mkv"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"video-data")
    create_response = await client.post(
        "/api/v1/tasks",
        json={**_paths_payload(series, source), "nfo_json": {"title": "启程", "season": 1, "episode": 2}},
    )
    task_id = create_response.json()["id"]
    commit_response = await client.post(f"/api/v1/tasks/{task_id}/commit")
    assert commit_response.status_code == 200
    await asyncio.sleep(0.1)

    response = await client.post(f"/api/v1/tasks/{task_id}/cancel")

    assert response.status_code == 400


async def test_cancel_missing_task_returns_404(client: AsyncClient) -> None:
    """不存在任务取消返回 404。"""

    response = await client.post("/api/v1/tasks/9999/cancel")

    assert response.status_code == 404


async def test_cover_raw_streams_staging_cover_file(client: AsyncClient, tmp_path: Path) -> None:
    series = await _create_series(client, tmp_path)
    source = tmp_path / "source" / "episode.mkv"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"video")
    create_response = await client.post(
        "/api/v1/tasks",
        json={**_paths_payload(series, source), "nfo_json": {"title": "启程", "season": 1, "episode": 2}},
    )
    task = create_response.json()
    jpeg = _make_jpeg_bytes()
    await client.post(
        f"/api/v1/tasks/{task['id']}/cover/upload",
        files={"file": ("cover.jpg", jpeg, "image/jpeg")},
    )

    response = await client.get(f"/api/v1/tasks/{task['id']}/cover/raw")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.content == jpeg


async def test_cover_raw_returns_404_when_task_missing(client: AsyncClient) -> None:
    response = await client.get("/api/v1/tasks/9999/cover/raw")

    assert response.status_code == 404


async def test_cover_raw_returns_404_when_cover_file_missing(client: AsyncClient, tmp_path: Path) -> None:
    series = await _create_series(client, tmp_path)
    source = tmp_path / "source" / "episode.mkv"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"video")
    create_response = await client.post(
        "/api/v1/tasks",
        json={**_paths_payload(series, source), "nfo_json": {"title": "启程", "season": 1, "episode": 2}},
    )
    task = create_response.json()

    response = await client.get(f"/api/v1/tasks/{task['id']}/cover/raw")

    assert response.status_code == 404


async def test_delete_draft_task_returns_204(
    client: AsyncClient, tmp_path: Path, test_engine: AsyncEngine
) -> None:
    """草稿任务允许删除。"""

    series = await _create_series(client, tmp_path)
    expected = _expected_paths(series)
    _write_staging_files(expected)
    maker = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        task = Task(
            status=TaskStatus.DRAFT,
            series_id=series["id"],
            series_name=series["name"],
            emby_series_id=series["emby_series_id"],
            library_id=series["library_id"],
            library_name=series["library_name"],
            season_number=1,
            episode_number=2,
            title="启程",
            source_file_path=str(tmp_path / "source" / "episode.mkv"),
            staging_video_path=expected["staging_video_path"],
            staging_nfo_path=expected["staging_nfo_path"],
            staging_cover_path=expected["staging_cover_path"],
            target_video_path=expected["target_video_path"],
            target_nfo_path=expected["target_nfo_path"],
            target_cover_path=expected["target_cover_path"],
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        task_id = task.id

    response = await client.delete(f"/api/v1/tasks/{task_id}")

    assert response.status_code == 204
    assert not Path(expected["staging_video_path"]).exists()
    assert not Path(expected["staging_nfo_path"]).exists()
    assert not Path(expected["staging_cover_path"]).exists()
    async with maker() as session:
        deleted = await session.get(Task, task_id)
        assert deleted is None


async def test_delete_staged_task_returns_204(
    client: AsyncClient, tmp_path: Path, test_engine: AsyncEngine
) -> None:
    """暂存任务允许删除并清理 staging 文件。"""

    series = await _create_series(client, tmp_path)
    expected = _expected_paths(series)
    _write_staging_files(expected)
    maker = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        task = Task(
            status=TaskStatus.DRAFT,
            series_id=series["id"],
            series_name=series["name"],
            emby_series_id=series["emby_series_id"],
            library_id=series["library_id"],
            library_name=series["library_name"],
            season_number=1,
            episode_number=2,
            title="启程",
            source_file_path=str(tmp_path / "source" / "episode.mkv"),
            staging_video_path=expected["staging_video_path"],
            staging_nfo_path=expected["staging_nfo_path"],
            staging_cover_path=expected["staging_cover_path"],
            target_video_path=expected["target_video_path"],
            target_nfo_path=expected["target_nfo_path"],
            target_cover_path=expected["target_cover_path"],
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        task_id = task.id

    response = await client.delete(f"/api/v1/tasks/{task_id}")

    assert response.status_code == 204
    assert not Path(expected["staging_video_path"]).exists()
    assert not Path(expected["staging_nfo_path"]).exists()
    assert not Path(expected["staging_cover_path"]).exists()
    async with maker() as session:
        deleted = await session.get(Task, task_id)
        assert deleted is None


async def test_delete_committed_task_returns_204(
    client: AsyncClient, tmp_path: Path, test_engine: AsyncEngine
) -> None:
    """已提交任务也允许删除，只删 DB 记录。"""

    series = await _create_series(client, tmp_path)
    source = tmp_path / "source" / "episode.mkv"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"video-data")
    create_response = await client.post(
        "/api/v1/tasks",
        json={**_paths_payload(series, source), "nfo_json": {"title": "启程", "season": 1, "episode": 2}},
    )
    task_id = create_response.json()["id"]

    commit_response = await client.post(f"/api/v1/tasks/{task_id}/commit")
    assert commit_response.status_code == 200
    await asyncio.sleep(0.1)

    async with async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)() as session:
        committed = await session.get(Task, task_id)
        assert committed is not None
        target_path = committed.target_video_path

    assert target_path is not None
    assert Path(target_path).exists()

    response = await client.delete(f"/api/v1/tasks/{task_id}")

    assert response.status_code == 204
    assert Path(target_path).exists()
    async with async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)() as session:
        deleted = await session.get(Task, task_id)
        assert deleted is None

