"""路径安全工具测试。

验证 ``safe_resolve`` 的路径遍历防护、``validate_inside_roots`` 的判定，
以及 ``PathSecurityError`` 自定义异常的抛出场景。
"""

import os
from pathlib import Path

import pytest

from app.utils.path_security import (
    PathSecurityError,
    safe_resolve,
    validate_inside_roots,
)


def test_safe_resolve_rejects_parent_traversal(tmp_path: Path) -> None:
    """``../../etc/passwd`` 风格路径必须被拒绝。"""

    with pytest.raises(PathSecurityError):
        safe_resolve("../../etc/passwd", [tmp_path])


def test_safe_resolve_accepts_real_path_under_root(tmp_path: Path) -> None:
    """root 下的子路径应当正常返回解析结果。"""

    sub = tmp_path / "Season 01" / "show.mkv"
    sub.parent.mkdir(parents=True)

    resolved = safe_resolve(sub, [tmp_path])

    assert resolved == sub.resolve(strict=False)


def test_safe_resolve_accepts_root_itself(tmp_path: Path) -> None:
    """path 与某个 root 完全相同时应当视为合法。"""

    resolved = safe_resolve(tmp_path, [tmp_path])

    assert resolved == tmp_path.resolve(strict=False)


def test_safe_resolve_rejects_symlink_pointing_outside(tmp_path: Path) -> None:
    """symlink 指向 allow-list 外时应当被拒绝。"""

    secret = tmp_path.parent / "secret.txt"
    secret.write_text("x", encoding="utf-8")
    try:
        link = tmp_path / "leak.txt"
        os.symlink(secret, link)

        with pytest.raises(PathSecurityError):
            safe_resolve(link, [tmp_path])
    finally:
        if secret.exists():
            secret.unlink()


def test_safe_resolve_empty_roots_rejected(tmp_path: Path) -> None:
    """没有任何 root 时应当抛错（不允许空 allow-list）。"""

    with pytest.raises(PathSecurityError):
        safe_resolve(tmp_path, [])


def test_validate_inside_roots_true(tmp_path: Path) -> None:
    """``validate_inside_roots`` 在合法路径上返回 ``True``。"""

    sub = tmp_path / "a.mp4"
    assert validate_inside_roots(sub, [tmp_path]) is True


def test_validate_inside_roots_false(tmp_path: Path) -> None:
    """root 外的路径返回 ``False``，不抛异常。"""

    other = tmp_path.parent / "outside.mp4"
    assert validate_inside_roots(other, [tmp_path]) is False


def test_validate_inside_roots_empty_roots(tmp_path: Path) -> None:
    """空 allow-list 一律返回 ``False``。"""

    assert validate_inside_roots(tmp_path, []) is False
