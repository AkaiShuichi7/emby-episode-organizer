"""文件浏览与源文件校验服务。

提供 :func:`browse_directory` 与 :func:`validate_source_file` 两个入口，
供前端文件选择器与后端业务流统一调用。所有路径访问都必须经过
:func:`safe_resolve` 校验，确保落在 ``allowed_roots`` 白名单内。

设计要点：
- ``BrowseResult`` 直接给出 ``parent_path``，前端无需自行拼接；
  当浏览路径本身就是某个 root 时 ``parent_path`` 为 ``None``，对应
  面包屑到顶的 UI 行为。
- 排序约定：目录优先，同类型内按 name 升序，便于 UI 默认展开展示。
- 目录的 ``is_video`` 永远为 ``False``，即便目录名恰好包含视频扩展名，
  避免前端误把目录当成可点播的视频。
- :class:`SourceFileInfo` 用于在后续 :func:`stage_files` 等接口前置确认
  源文件存在、是文件且扩展名在视频白名单内。
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from app.utils.filename import get_file_extension, is_video_file
from app.utils.path_security import safe_resolve

logger = logging.getLogger(__name__)


class BrowseEntry(BaseModel):
    """目录浏览列表中的单个条目。

    属性:
        name: 条目名称（不含父路径）。
        path: 条目绝对路径，前端点击时传回后端用于导航。
        is_dir: 是否为目录。
        is_video: 是否为视频文件；目录恒为 ``False``。
        size: 文件字节数；目录也取 ``stat().st_size``，便于 UI 排序展示。
        modified_at: 最后修改时间（naive 本地时间）。
    """

    name: str
    path: Path
    is_dir: bool
    is_video: bool
    size: int
    modified_at: datetime = Field(default_factory=lambda: datetime.fromtimestamp(0))


class BrowseResult(BaseModel):
    """目录浏览结果。

    属性:
        current_path: 已解析的当前目录绝对路径。
        parent_path: 父目录绝对路径；当前目录本身已是 root 时为 ``None``。
        entries: 当前目录下的条目列表，已按"目录优先 + name 升序"排序。
    """

    current_path: Path
    parent_path: Path | None
    entries: list[BrowseEntry]


class SourceFileInfo(BaseModel):
    """源视频文件校验结果。

    属性:
        path: 解析后的绝对路径，已确认落在 ``allowed_roots`` 内。
        size: 文件字节数。
        extension: 小写扩展名，含前导 ``.``，便于后续逻辑分支。
        is_video: 是否落在视频白名单内，本结构使用时恒为 ``True``。
    """

    path: Path
    size: int
    extension: str
    is_video: bool


class NotAVideoError(Exception):
    """源路径不是视频文件时抛出。"""

    path: Path | None

    def __init__(self, message: str, *, path: Path | None = None) -> None:
        """构造异常。

        参数:
            message: 人类可读错误描述。
            path: 出错的源路径，可选。

        返回:
            None
        """

        super().__init__(message)
        self.path = path


def _normalize_roots(allowed_roots: list[Path]) -> list[Path]:
    """把所有 root 解析为绝对路径，便于 ``in`` 比较。"""

    return [root.expanduser().resolve(strict=False) for root in allowed_roots]


def _build_entry(entry: Path) -> BrowseEntry:
    """根据 ``Path`` 构造 :class:`BrowseEntry`。"""

    stat = entry.stat()
    is_dir = entry.is_dir()
    # ponytail: 目录永远不是视频，避免目录名带 .mkv/.mp4 时被误识别。
    is_video = (not is_dir) and is_video_file(entry)
    return BrowseEntry(
        name=entry.name,
        path=entry,
        is_dir=is_dir,
        is_video=is_video,
        size=stat.st_size,
        modified_at=datetime.fromtimestamp(stat.st_mtime),
    )


def browse_directory(path: str | Path, allowed_roots: list[Path]) -> BrowseResult:
    """列出 ``path`` 下的目录与文件。

    流程：
    1. 用 :func:`safe_resolve` 把 ``path`` 解析为绝对路径并校验白名单。
    2. 不存在时直接抛 builtin :class:`FileNotFoundError`。
    3. 解析 ``parent_path``：当前路径本身就是某个 root 时为 ``None``。
    4. ``iterdir`` 遍历子条目，按"目录优先 + name 升序"排序后返回。

    参数:
        path: 待浏览的目录路径，可以是 ``str`` 或 :class:`Path`。
        allowed_roots: 允许的根目录列表。

    返回:
        :class:`BrowseResult`，含当前路径、父路径与条目列表。

    抛出:
        PathSecurityError: ``path`` 不在 ``allowed_roots`` 内或 ``allowed_roots`` 为空。
        FileNotFoundError: ``path`` 解析后不存在。
    """

    resolved = safe_resolve(path, allowed_roots)
    if not resolved.exists() or not resolved.is_dir():
        raise FileNotFoundError(f"目录不存在: {resolved}")

    normalized_roots = _normalize_roots(allowed_roots)
    parent_path: Path | None = None if resolved in normalized_roots else resolved.parent

    raw_entries = sorted(resolved.iterdir(), key=lambda p: p.name.lower())
    entries: list[BrowseEntry] = []
    for child in raw_entries:
        try:
            entries.append(_build_entry(child))
        except OSError as exc:  # pragma: no cover - 权限/损坏 symlink 等极端情况
            logger.warning("浏览目录跳过无法读取的条目: path=%s err=%s", child, exc)
            continue

    # ponytail: 排序再覆盖一次，确保目录排在文件之前，name 升序。
    entries.sort(key=lambda e: (not e.is_dir, e.name.lower()))

    logger.debug(
        "目录浏览完成: current=%s parent=%s entries=%d",
        resolved,
        parent_path,
        len(entries),
    )
    return BrowseResult(
        current_path=resolved,
        parent_path=parent_path,
        entries=entries,
    )


def validate_source_file(path: str | Path, allowed_roots: list[Path]) -> SourceFileInfo:
    """校验 ``path`` 是一个可用的视频源文件。

    流程：
    1. :func:`safe_resolve` 校验路径合法。
    2. 文件不存在抛 builtin :class:`FileNotFoundError`。
    3. 是目录或扩展名不在视频白名单内抛 :class:`NotAVideoError`。

    参数:
        path: 待校验的源文件路径。
        allowed_roots: 允许的根目录列表。

    返回:
        :class:`SourceFileInfo`，含路径、大小、扩展名。

    抛出:
        PathSecurityError: ``path`` 不在 ``allowed_roots`` 内或 ``allowed_roots`` 为空。
        FileNotFoundError: 文件不存在。
        NotAVideoError: 路径指向目录或扩展名不在视频白名单内。
    """

    resolved = safe_resolve(path, allowed_roots)

    if not resolved.exists():
        raise FileNotFoundError(f"源文件不存在: {resolved}")
    if not resolved.is_file():
        raise NotAVideoError(f"源路径不是文件: {resolved}", path=resolved)

    extension = get_file_extension(resolved)
    if not is_video_file(resolved):
        raise NotAVideoError(
            f"源文件不是支持的视频格式: {resolved} (扩展名={extension!r})",
            path=resolved,
        )

    size = resolved.stat().st_size
    logger.info(
        "源视频校验通过: path=%s size=%d extension=%s",
        resolved,
        size,
        extension,
    )
    return SourceFileInfo(
        path=resolved,
        size=size,
        extension=extension,
        is_video=True,
    )
