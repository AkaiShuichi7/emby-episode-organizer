"""文件暂存与原子提交服务。

负责把源视频、NFO、封面复制到 staging，再通过同目录 ``.tmp`` 文件和
``os.rename`` 原子落地到目标目录。失败时保留 staging，便于后续重试。
"""

from __future__ import annotations

import errno
import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from app.utils.filename import is_video_file
from app.utils.path_security import PathSecurityError, safe_resolve

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StageResult:
    """文件暂存结果。

    属性:
        video_path: staging 内的视频路径。
        nfo_path: staging 内的 NFO 路径。
        cover_path: staging 内的封面路径；无封面时为 ``None``。
        sizes: 已写入文件大小，key 为落盘路径，value 为字节数。
    """

    video_path: Path
    nfo_path: Path
    cover_path: Path | None
    sizes: dict[Path, int]


@dataclass(frozen=True, slots=True)
class CommitResult:
    """目标提交结果。

    属性:
        target_files: 成功落地的目标文件路径，顺序与 staging 文件一致。
        sizes: 已提交目标文件大小，key 为目标路径，value 为字节数。
    """

    target_files: list[Path]
    sizes: dict[Path, int]


class FileConflictError(Exception):
    """目标目录已有同名文件时抛出。"""


class MovePermissionError(Exception):
    """源文件不可用、路径非法或权限不足时抛出。"""


class DiskFullError(Exception):
    """复制后大小不一致或磁盘空间不足时抛出。"""


def _resolve_directory(path: Path) -> Path:
    """解析目录自身路径。

    参数:
        path: 待解析目录。

    返回:
        解析后的绝对路径。

    抛出:
        MovePermissionError: 路径解析失败时抛出。
    """

    try:
        return safe_resolve(path, [path])
    except PathSecurityError as exc:
        raise MovePermissionError(f"路径非法: {path}") from exc


def _resolve_child(parent: Path, filename: str) -> Path:
    """把文件名解析为 parent 下的直接子文件。

    参数:
        parent: 父目录。
        filename: 文件名，不允许绝对路径或 ``..``。

    返回:
        位于 parent 下的目标文件路径。

    抛出:
        MovePermissionError: 文件名尝试逃逸父目录时抛出。
    """

    name = Path(filename)
    if name.is_absolute() or name.name != filename or ".." in name.parts:
        raise MovePermissionError(f"文件名非法: {filename}")

    try:
        return safe_resolve(parent / filename, [parent])
    except PathSecurityError as exc:
        raise MovePermissionError(f"文件路径不在目标目录内: {filename}") from exc


def _tmp_path(target_path: Path) -> Path:
    """生成目标同目录 ``.tmp`` 路径。"""

    return target_path.with_name(f"{target_path.name}.tmp")


def _size(path: Path) -> int:
    """读取文件大小，统一返回字节数。"""

    return path.stat().st_size


def _map_os_error(exc: OSError, action: str) -> Exception:
    """把底层 OSError 映射成业务异常。"""

    if exc.errno == errno.ENOSPC:
        return DiskFullError(f"{action}失败: 磁盘空间不足")
    if isinstance(exc, PermissionError) or exc.errno in {errno.EACCES, errno.EPERM}:
        return MovePermissionError(f"{action}失败: 权限不足")
    return MovePermissionError(f"{action}失败: {exc}")


def _cleanup(paths: list[Path], reason: str) -> None:
    """删除失败流程中的临时文件。"""

    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:  # pragma: no cover - 极端磁盘错误
            logger.warning("清理失败残留文件失败: path=%s reason=%s err=%s", path, reason, exc)


def _validate_source_video(source_video: Path) -> Path:
    """校验源视频存在、是文件、扩展名在视频白名单内。"""

    source = _resolve_directory(source_video)
    if not source.exists() or not source.is_file():
        raise MovePermissionError(f"源视频不存在或不是文件: {source_video}")
    if not is_video_file(source):
        raise MovePermissionError(f"源文件不是支持的视频格式: {source_video}")
    return source


async def stage_files(
    source_video: Path,
    staging_dir: Path,
    nfo_xml: str,
    cover_source: Path | None,
    *,
    video_filename: str,
    nfo_filename: str,
    cover_filename: str | None = None,
) -> StageResult:
    """把源视频、NFO、可选封面写入 staging 目录。

    参数:
        source_video: 已选择的源视频路径，必须存在且扩展名在视频白名单内。
        staging_dir: 暂存目录；不存在时自动创建。
        nfo_xml: 要写入的 NFO XML 文本。
        cover_source: 可选封面源文件；为 ``None`` 或不存在时跳过封面。
        video_filename: staging 内视频文件名。
        nfo_filename: staging 内 NFO 文件名。
        cover_filename: staging 内封面文件名；有封面源文件时必须提供。

    返回:
        :class:`StageResult`，包含三个产物路径和文件大小。

    抛出:
        MovePermissionError: 源视频不存在、不是视频、文件名非法或权限不足。
        DiskFullError: 复制过程发现磁盘空间不足。
    """

    source = _validate_source_video(source_video)
    staging = _resolve_directory(staging_dir)
    video_path = _resolve_child(staging, video_filename)
    nfo_path = _resolve_child(staging, nfo_filename)

    try:
        staging.mkdir(parents=True, exist_ok=True)
        # ponytail: 大文件复制交给 shutil.copy2，避免一次性读入内存，也保留 mtime。
        _ = shutil.copy2(source, video_path)
        _ = nfo_path.write_text(nfo_xml, encoding="utf-8")

        cover_path: Path | None = None
        if cover_source is not None and cover_source.exists():
            if cover_filename is None:
                raise MovePermissionError("有封面源文件时必须提供 cover_filename")
            cover_path = _resolve_child(staging, cover_filename)
            _ = shutil.copy2(cover_source, cover_path)
    except OSError as exc:
        raise _map_os_error(exc, "暂存文件") from exc

    sizes = {video_path: _size(video_path), nfo_path: _size(nfo_path)}
    if cover_path is not None:
        sizes[cover_path] = _size(cover_path)

    logger.info(
        "文件暂存完成: source=%s staging=%s video=%s nfo=%s cover=%s",
        source,
        staging,
        video_path,
        nfo_path,
        cover_path,
    )
    return StageResult(
        video_path=video_path,
        nfo_path=nfo_path,
        cover_path=cover_path,
        sizes=sizes,
    )


async def commit_to_target(staging_files: list[Path], target_dir: Path) -> CommitResult:
    """把 staging 文件原子提交到目标目录。

    流程先复制所有 staging 文件到目标同目录 ``.tmp``，逐个校验大小，再用
    ``os.rename`` 改名为最终文件。所有目标文件落地后才删除 staging 文件，
    因此任一步失败都会清理 ``.tmp`` 并保留 staging，供后续重试。

    参数:
        staging_files: 待提交的 staging 文件列表。
        target_dir: 目标目录；不存在时自动创建。

    返回:
        :class:`CommitResult`，包含目标文件路径和大小。

    抛出:
        FileConflictError: 任一目标文件已存在。
        MovePermissionError: staging 文件缺失、权限不足或路径非法。
        DiskFullError: 复制后大小不一致或磁盘空间不足。
    """

    target = _resolve_directory(target_dir)
    files = [_resolve_directory(path) for path in staging_files]
    target_files = [_resolve_child(target, path.name) for path in files]

    for source in files:
        if not source.exists() or not source.is_file():
            raise MovePermissionError(f"staging 文件不存在或不是文件: {source}")

    conflicts = [path for path in target_files if path.exists()]
    if conflicts:
        logger.warning("目标文件冲突，保留 staging: conflicts=%s", conflicts)
        raise FileConflictError(f"目标文件已存在: {[str(path) for path in conflicts]}")

    tmp_files = [_tmp_path(path) for path in target_files]
    created_targets: list[Path] = []

    try:
        target.mkdir(parents=True, exist_ok=True)
        for source, tmp in zip(files, tmp_files, strict=True):
            # ponytail: 复制走 shutil.copy2，不手写 chunk 复制，避免 1GB+ 文件进内存。
            _ = shutil.copy2(source, tmp)
            if _size(tmp) != _size(source):
                raise DiskFullError(f"复制大小不一致: source={source} tmp={tmp}")

        for tmp, final in zip(tmp_files, target_files, strict=True):
            # ponytail: tmp 与最终文件同目录，os.rename 在同一文件系统内原子切换。
            os.rename(tmp, final)
            created_targets.append(final)

        sizes = {path: _size(path) for path in target_files}
        for source in files:
            source.unlink()
    except OSError as exc:
        _cleanup(tmp_files, "commit OSError")
        _cleanup(created_targets, "commit OSError")
        logger.error("文件提交失败，状态应置为 failed: target=%s err=%s", target, exc)
        raise _map_os_error(exc, "提交文件") from exc
    except (DiskFullError, MovePermissionError):
        _cleanup(tmp_files, "commit business error")
        _cleanup(created_targets, "commit business error")
        logger.error("文件提交失败，状态应置为 failed: target=%s", target)
        raise

    logger.info("文件提交完成: target=%s files=%s", target, target_files)
    return CommitResult(target_files=target_files, sizes=sizes)


async def cancel_staging(staging_dir: Path) -> bool:
    """取消暂存并删除整个 staging 目录。

    参数:
        staging_dir: 要删除的暂存目录。

    返回:
        ``True`` 表示调用完成。目录不存在也视为取消成功。

    抛出:
        MovePermissionError: 路径非法或删除权限不足。
    """

    staging = _resolve_directory(staging_dir)
    try:
        shutil.rmtree(staging, ignore_errors=True)
    except OSError as exc:
        raise _map_os_error(exc, "取消暂存") from exc

    logger.info("暂存目录已取消: staging=%s", staging)
    return True
