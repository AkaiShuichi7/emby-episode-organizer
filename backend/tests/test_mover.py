"""文件移动服务测试。

用 tmp_path 和真实文件系统覆盖暂存、提交、冲突、回滚和取消流程。
"""

# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from app.services.mover import (
    DiskFullError,
    FileConflictError,
    MovePermissionError,
    cancel_staging,
    commit_to_target,
    stage_files,
)


def _write_file(path: Path, content: bytes) -> Path:
    """写入测试文件并返回路径。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_bytes(content)
    return path


def _md5(path: Path) -> str:
    """计算文件 MD5，用于确认复制内容完全一致。"""

    return hashlib.md5(path.read_bytes(), usedforsecurity=False).hexdigest()


async def test_stage_files_writes_video_nfo_and_cover(tmp_path: Path) -> None:
    """stage_files 生成视频、NFO、封面，路径和内容正确。"""

    source_video = _write_file(tmp_path / "source" / "episode.mkv", b"video-data")
    cover_source = _write_file(tmp_path / "source" / "cover.jpg", b"cover-data")
    staging_dir = tmp_path / "staging" / "task-1"
    nfo_xml = "<episodedetails><title>第一集</title></episodedetails>"

    result = await stage_files(
        source_video,
        staging_dir,
        nfo_xml,
        cover_source,
        video_filename="剧集 - S01E01 - 第一集.mkv",
        nfo_filename="剧集 - S01E01 - 第一集.nfo",
        cover_filename="剧集 - S01E01 - 第一集-thumb.jpg",
    )

    assert result.video_path == staging_dir / "剧集 - S01E01 - 第一集.mkv"
    assert result.nfo_path == staging_dir / "剧集 - S01E01 - 第一集.nfo"
    assert result.cover_path == staging_dir / "剧集 - S01E01 - 第一集-thumb.jpg"
    assert _md5(result.video_path) == _md5(source_video)
    assert result.nfo_path.read_text(encoding="utf-8") == nfo_xml
    assert result.cover_path is not None
    assert _md5(result.cover_path) == _md5(cover_source)
    assert result.sizes == {
        result.video_path: len(b"video-data"),
        result.nfo_path: len(nfo_xml.encode("utf-8")),
        result.cover_path: len(b"cover-data"),
    }


async def test_stage_files_without_cover_skips_cover(tmp_path: Path) -> None:
    """cover_source 为 None 时不生成封面文件。"""

    source_video = _write_file(tmp_path / "source" / "episode.mp4", b"video-data")
    staging_dir = tmp_path / "staging" / "task-1"

    result = await stage_files(
        source_video,
        staging_dir,
        "<episodedetails />",
        None,
        video_filename="episode.mp4",
        nfo_filename="episode.nfo",
        cover_filename="episode-thumb.jpg",
    )

    assert result.cover_path is None
    assert not (staging_dir / "episode-thumb.jpg").exists()
    assert result.sizes == {
        result.video_path: len(b"video-data"),
        result.nfo_path: len(b"<episodedetails />"),
    }


async def test_commit_to_target_moves_all_files_and_deletes_staging(
    tmp_path: Path,
) -> None:
    """commit_to_target 提交后目标目录有三文件，暂存文件被删除。"""

    staging_dir = tmp_path / "staging"
    video = _write_file(staging_dir / "episode.mkv", b"video-data")
    nfo = _write_file(staging_dir / "episode.nfo", b"nfo-data")
    cover = _write_file(staging_dir / "episode-thumb.jpg", b"cover-data")
    target_dir = tmp_path / "target"

    result = await commit_to_target([video, nfo, cover], target_dir)

    target_files = [target_dir / path.name for path in (video, nfo, cover)]
    assert result.target_files == target_files
    assert result.sizes == {
        target_files[0]: len(b"video-data"),
        target_files[1]: len(b"nfo-data"),
        target_files[2]: len(b"cover-data"),
    }
    assert [path.exists() for path in (video, nfo, cover)] == [False, False, False]
    assert [path.read_bytes() for path in target_files] == [
        b"video-data",
        b"nfo-data",
        b"cover-data",
    ]


async def test_commit_to_target_conflict_keeps_staging(tmp_path: Path) -> None:
    """目标同名文件已存在时抛 FileConflictError 且保留 staging。"""

    staging_dir = tmp_path / "staging"
    video = _write_file(staging_dir / "episode.mkv", b"video-data")
    nfo = _write_file(staging_dir / "episode.nfo", b"nfo-data")
    target_dir = tmp_path / "target"
    _ = _write_file(target_dir / "episode.mkv", b"existing")

    with pytest.raises(FileConflictError):
        await commit_to_target([video, nfo], target_dir)

    assert video.read_bytes() == b"video-data"
    assert nfo.read_bytes() == b"nfo-data"
    assert (target_dir / "episode.mkv").read_bytes() == b"existing"
    assert not (target_dir / "episode.nfo").exists()


async def test_commit_to_target_size_mismatch_cleans_tmp_and_keeps_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """提交中源文件大小变化时失败，清理 .tmp 并保留 staging。"""

    staging_dir = tmp_path / "staging"
    video = _write_file(staging_dir / "episode.mkv", b"video-data")
    target_dir = tmp_path / "target"
    original_copy2 = shutil.copy2

    def copy2_and_mutate(
        src: str | Path,
        dst: str | Path,
        *,
        follow_symlinks: bool = True,
    ) -> str | Path:
        copied = original_copy2(src, dst, follow_symlinks=follow_symlinks)
        if Path(src) == video:
            _ = video.write_bytes(b"video-data-changed")
        return copied

    monkeypatch.setattr(shutil, "copy2", copy2_and_mutate)

    with pytest.raises(DiskFullError):
        await commit_to_target([video], target_dir)

    assert video.read_bytes() == b"video-data-changed"
    assert not (target_dir / "episode.mkv.tmp").exists()
    assert not (target_dir / "episode.mkv").exists()


async def test_cancel_staging_removes_directory(tmp_path: Path) -> None:
    """cancel_staging 删除整个暂存目录。"""

    staging_dir = tmp_path / "staging" / "task-1"
    _ = _write_file(staging_dir / "nested" / "episode.mkv", b"video-data")

    removed = await cancel_staging(staging_dir)

    assert removed is True
    assert not staging_dir.exists()


async def test_stage_files_missing_source_raises(tmp_path: Path) -> None:
    """源视频不存在时抛 MovePermissionError。"""

    with pytest.raises(MovePermissionError):
        await stage_files(
            tmp_path / "missing.mkv",
            tmp_path / "staging",
            "<episodedetails />",
            None,
            video_filename="missing.mkv",
            nfo_filename="missing.nfo",
        )


async def test_stage_files_non_video_source_raises(tmp_path: Path) -> None:
    """源文件不是视频扩展名时抛 MovePermissionError。"""

    source = _write_file(tmp_path / "source" / "notes.txt", b"not-video")

    with pytest.raises(MovePermissionError):
        await stage_files(
            source,
            tmp_path / "staging",
            "<episodedetails />",
            None,
            video_filename="notes.txt",
            nfo_filename="notes.nfo",
        )
