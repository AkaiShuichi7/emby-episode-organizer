"""文件浏览服务测试。

验证 ``browse_directory`` 在目录列表、路径安全、排序、错误分支上的行为，
以及 ``validate_source_file`` 对源视频文件的强校验流程。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.files import (
    BrowseEntry,
    BrowseResult,
    NotAVideoError,
    SourceFileInfo,
    browse_directory,
    validate_source_file,
)
from app.utils.path_security import PathSecurityError


def _populate_source_root(root: Path) -> None:
    """在 ``root`` 下造一组典型素材：3 文件 + 1 子目录。

    - ``episode01.mp4`` / ``episode02.mkv`` / ``notes.txt``
    - ``Season 01/`` 子目录，目录内含一个视频用于演练排序

    """

    _ = (root / "episode01.mp4").write_bytes(b"a" * 10)
    _ = (root / "episode02.mkv").write_bytes(b"b" * 20)
    _ = (root / "notes.txt").write_text("metadata", encoding="utf-8")
    season_dir = root / "Season 01"
    season_dir.mkdir()
    _ = (season_dir / "inner.mp4").write_bytes(b"c" * 30)


def test_browse_lists_mixed_entries(tmp_path: Path) -> None:
    """混合目录与文件时，``is_dir`` / ``is_video`` 标记必须正确。"""

    _populate_source_root(tmp_path)

    result = browse_directory(tmp_path, [tmp_path])

    assert isinstance(result, BrowseResult)
    assert result.current_path == tmp_path.resolve(strict=False)
    by_name = {entry.name: entry for entry in result.entries}

    assert set(by_name) == {"episode01.mp4", "episode02.mkv", "notes.txt", "Season 01"}

    ep1 = by_name["episode01.mp4"]
    assert ep1.is_dir is False
    assert ep1.is_video is True
    assert ep1.path == tmp_path.resolve(strict=False) / "episode01.mp4"
    assert ep1.size == 10
    assert isinstance(ep1, BrowseEntry)

    notes = by_name["notes.txt"]
    assert notes.is_dir is False
    assert notes.is_video is False
    assert notes.size == len(b"metadata")

    season = by_name["Season 01"]
    assert season.is_dir is True
    # ponytail: 目录永远不是视频，即使名字带视频扩展名也不算数
    assert season.is_video is False


def test_browse_sorts_directories_first(tmp_path: Path) -> None:
    """``browse_directory`` 排序：目录在前，同类型内按 name 升序。"""

    _populate_source_root(tmp_path)

    result = browse_directory(tmp_path, [tmp_path])

    names = [entry.name for entry in result.entries]
    assert names[0] == "Season 01"
    # 文件按字典序排列
    assert names[1:] == ["episode01.mp4", "episode02.mkv", "notes.txt"]


def test_browse_empty_directory_returns_empty_entries(tmp_path: Path) -> None:
    """空目录浏览应返回 ``entries=[]``，但 current_path 仍可用。"""

    result = browse_directory(tmp_path, [tmp_path])

    assert result.entries == []
    assert result.current_path == tmp_path.resolve(strict=False)


def test_browse_root_itself_has_no_parent(tmp_path: Path) -> None:
    """browse 的路径本身就是 allowed_root 时，``parent_path`` 为 ``None``。"""

    result = browse_directory(tmp_path, [tmp_path])

    assert result.parent_path is None


def test_browse_subdirectory_has_parent(tmp_path: Path) -> None:
    """browse 子目录时，``parent_path`` 应等于 current_path 的父目录。"""

    sub = tmp_path / "Season 01"
    sub.mkdir()
    _ = (sub / "ep.mp4").write_bytes(b"x" * 5)

    result = browse_directory(sub, [tmp_path])

    assert result.parent_path == tmp_path.resolve(strict=False)


def test_browse_outside_allowed_roots_rejected(tmp_path: Path) -> None:
    """browse 路径不在 allowed_roots 内时，必须抛 :class:`PathSecurityError`。"""

    other_root = tmp_path / "elsewhere"
    other_root.mkdir()
    _ = (other_root / "a.mp4").write_bytes(b"x")

    with pytest.raises(PathSecurityError):
        _ = browse_directory(other_root, [tmp_path / "staging"])


def test_browse_missing_directory_raises_file_not_found(tmp_path: Path) -> None:
    """browse 一个不存在的目录，抛 Python builtin :class:`FileNotFoundError`。"""

    ghost = tmp_path / "does_not_exist"

    with pytest.raises(FileNotFoundError):
        _ = browse_directory(ghost, [tmp_path])


def test_validate_video_file_returns_source_info(tmp_path: Path) -> None:
    """合法视频文件返回 :class:`SourceFileInfo`，字段与真实文件一致。"""

    target = tmp_path / "Episode01.mp4"
    _ = target.write_bytes(b"x" * 42)

    info = validate_source_file(target, [tmp_path])

    assert isinstance(info, SourceFileInfo)
    assert info.path == target.resolve(strict=False)
    assert info.extension == ".mp4"
    assert info.is_video is True
    assert info.size == 42


def test_validate_uppercase_extension_accepted(tmp_path: Path) -> None:
    """扩展名大小写不敏感，``.MKV`` 仍被识别为视频。"""

    target = tmp_path / "movie.MKV"
    _ = target.write_bytes(b"y" * 8)

    info = validate_source_file(target, [tmp_path])

    assert info.is_video is True
    assert info.extension == ".mkv"


def test_validate_non_video_extension_rejected(tmp_path: Path) -> None:
    """非视频扩展名抛 :class:`NotAVideoError`。"""

    target = tmp_path / "notes.txt"
    _ = target.write_text("hello", encoding="utf-8")

    with pytest.raises(NotAVideoError):
        _ = validate_source_file(target, [tmp_path])


def test_validate_directory_rejected(tmp_path: Path) -> None:
    """目录不能作为源视频，抛 :class:`NotAVideoError`。"""

    sub = tmp_path / "Season 01"
    sub.mkdir()

    with pytest.raises(NotAVideoError):
        _ = validate_source_file(sub, [tmp_path])


def test_validate_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    """文件不存在抛 builtin :class:`FileNotFoundError`。"""

    ghost = tmp_path / "missing.mp4"

    with pytest.raises(FileNotFoundError):
        _ = validate_source_file(ghost, [tmp_path])


def test_validate_outside_allowed_roots_rejected(tmp_path: Path) -> None:
    """源文件路径不在 allowed_roots 时抛 :class:`PathSecurityError`。"""

    outside = tmp_path.parent / "outside.mp4"
    _ = outside.write_bytes(b"x")

    try:
        with pytest.raises(PathSecurityError):
            _ = validate_source_file(outside, [tmp_path])
    finally:
        if outside.exists():
            outside.unlink()
