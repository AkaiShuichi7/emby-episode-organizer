"""路径安全工具。

对外暴露 ``safe_resolve`` 与 ``validate_inside_roots`` 两个函数，用于在文件系统操作前
统一校验路径是否落在允许的根目录集合内，从而阻断路径遍历与恶意 symlink 攻击。
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class PathSecurityError(Exception):
    """路径校验失败时抛出的异常。

    典型场景：路径在 ``allowed_roots`` 之外、``allowed_roots`` 为空、symlink 指向允许区域之外。
    """


def _normalize_root(root: Path) -> Path:
    """将 root 解析为绝对路径，不要求存在。"""

    return root.resolve(strict=False)


def safe_resolve(path: str | Path, allowed_roots: list[Path]) -> Path:
    """把 ``path`` 解析为绝对路径，并校验它位于任一 ``allowed_roots`` 下。

    - 解析使用 ``Path.resolve(strict=False)``，允许最终目标不存在但会跟随 symlink。
    - 当 ``allowed_roots`` 为空，或解析结果不在任一 root 之下时，抛出 :class:`PathSecurityError`。
    - root 本身被视为合法。

    参数:
        path: 待校验的路径，可以是 ``str`` 或 :class:`Path`。
        allowed_roots: 允许的根目录列表，必须为非空。

    返回:
        解析后的绝对 :class:`Path`，已确认位于允许区域内。

    抛出:
        PathSecurityError: 当路径不在允许区域或 allow-list 为空时。

    注解:
        业务侧所有文件读写的入口都必须先经过本函数，避免引入目录遍历漏洞。
    """

    if not allowed_roots:
        raise PathSecurityError("allowed_roots 不能为空，必须配置至少一个允许根目录")

    resolved_input = Path(path).expanduser().resolve(strict=False)

    normalized_roots = [_normalize_root(root) for root in allowed_roots]
    for root in normalized_roots:
        if resolved_input == root or resolved_input.is_relative_to(root):
            logger.debug("路径校验通过: %s 位于 root=%s", resolved_input, root)
            return resolved_input

    raise PathSecurityError(
        f"路径 {resolved_input} 不在允许的根目录内: "
        f"{[str(r) for r in normalized_roots]}"
    )


def validate_inside_roots(path: Path, roots: list[Path]) -> bool:
    """判断 ``path`` 是否在 ``roots`` 任意一个根目录之下。

    与 :func:`safe_resolve` 的语义一致，但不抛异常，仅返回布尔值，便于业务层做条件分支。

    参数:
        path: 待检查的 :class:`Path`。
        roots: 允许的根目录列表；为空时始终返回 ``False``。

    返回:
        ``True`` 表示路径落在任一 root 内（含自身），``False`` 表示不在。
    """

    if not roots:
        return False

    try:
        resolved = path.expanduser().resolve(strict=False)
    except (OSError, RuntimeError):
        # Path.resolve 在权限或循环 symlink 等极端情况下可能抛错
        return False

    return any(
        resolved == root or resolved.is_relative_to(root)
        for root in (_normalize_root(r) for r in roots)
    )
