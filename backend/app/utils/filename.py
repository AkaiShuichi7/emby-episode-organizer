"""文件名清理与扩展名识别。

集中提供 ``sanitize_filename`` / ``sanitize_series_name`` 等字符串清洗函数，
以及基于白名单的视频扩展名判定，供命名模板 (T6) 与后续业务复用。
"""

from __future__ import annotations

import re
from pathlib import Path

#: 视频文件扩展名白名单，统一小写且包含前导 ``.``。
VIDEO_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".mp4",
        ".mkv",
        ".avi",
        ".mov",
        ".wmv",
        ".flv",
        ".ts",
        ".m2ts",
        ".webm",
    }
)

#: 文件名中需替换为下划线的 Windows 非法字符集合。
_ILLEGAL_CHARS = re.compile(r'[\\/:*?"<>|]')

#: 连续空白字符（含制表符等），最终统一折叠为单个空格。
_MULTI_WHITESPACE = re.compile(r"\s+")

#: ``sanitize_series_name`` 在合法字符之外额外禁止 ``.``，避免目录名被当作扩展名。
_SERIES_DOT = re.compile(r"\.")


def _finalize(name: str) -> str:
    """应用最后一轮规则：合并空白、去首尾空格、决定默认占位符。"""

    collapsed = _MULTI_WHITESPACE.sub(" ", name).strip()
    if not collapsed or set(collapsed) <= {"_", " "}:
        return "Untitled"
    return collapsed


def sanitize_filename(name: str) -> str:
    """清洗文件名，保留中文 / 英文 / 数字 / 空格 / ``-`` / ``()`` / ``[]`` / ``.``。

    具体处理：

    - 将 ``\\ / : * ? " < > |`` 替换为 ``_``。
    - 合并连续空白并去掉首尾空格。
    - 全部被替换为空时返回 ``"Untitled"``。

    参数:
        name: 原始文件名，通常来自第三方元数据或用户输入。

    返回:
        符合 NTFS / ext4 通用规则的安全文件名。
    """

    if not name:
        return "Untitled"
    replaced = _ILLEGAL_CHARS.sub("_", name)
    return _finalize(replaced)


def sanitize_series_name(name: str) -> str:
    """清洗剧集系列名。

    在 :func:`sanitize_filename` 的基础上额外移除 ``.``，避免目录名被误读为扩展名。
    主要用于季目录与剧集根目录的命名。

    参数:
        name: 原始系列名。

    返回:
        不含点号的安全目录名。
    """

    base = sanitize_filename(name)
    return _SERIES_DOT.sub("", base)


def get_file_extension(path: Path) -> str:
    """提取小写扩展名，始终包含前导 ``.``；无扩展名返回空串。"""

    return path.suffix.lower()


def is_video_file(path: Path) -> bool:
    """判断 ``path`` 是否落在 :data:`VIDEO_EXTENSIONS` 白名单内。"""

    return get_file_extension(path) in VIDEO_EXTENSIONS
