"""文件名清理工具测试。

验证 ``sanitize_*`` 在非法字符、连续空格、纯特殊字符、中文等场景下的行为，
以及 ``get_file_extension`` / ``is_video_file`` 的扩展名识别。
"""

from pathlib import Path

from app.utils.filename import (
    VIDEO_EXTENSIONS,
    get_file_extension,
    is_video_file,
    sanitize_filename,
    sanitize_series_name,
)


def test_sanitize_filename_replaces_illegal_chars() -> None:
    """Windows 非法字符全部替换为下划线。"""

    assert sanitize_filename('a:b\\c/d*e?f"g<h>i|j.mp4') == "a_b_c_d_e_f_g_h_i_j.mp4"


def test_sanitize_filename_keeps_chinese() -> None:
    """中文与数字必须原样保留。"""

    assert sanitize_filename("三叉戟 2024 S01E03") == "三叉戟 2024 S01E03"


def test_sanitize_filename_collapses_spaces() -> None:
    """连续空格合并为单个空格。"""

    assert sanitize_filename("a   b   c") == "a b c"


def test_sanitize_filename_strips_outer_spaces() -> None:
    """首尾空格被去除。"""

    assert sanitize_filename("  hello  ") == "hello"


def test_sanitize_filename_pure_special_returns_untitled() -> None:
    """纯特殊字符清洗后为空时返回 ``Untitled``。"""

    assert sanitize_filename("///") == "Untitled"
    assert sanitize_filename("") == "Untitled"


def test_sanitize_filename_preserves_brackets_and_dashes() -> None:
    """``-`` ``()`` ``[]`` 应当保留。"""

    assert sanitize_filename("Show (2024) - vol.1 [remux]") == "Show (2024) - vol.1 [remux]"


def test_sanitize_series_name_strips_dot() -> None:
    """``sanitize_series_name`` 不允许 ``.``，用于目录名。"""

    assert sanitize_series_name("Series.Name") == "SeriesName"


def test_sanitize_series_name_keeps_chinese() -> None:
    """``sanitize_series_name`` 同样保留中文与连字符。"""

    assert sanitize_series_name("三叉戟-Season.01") == "三叉戟-Season01"


def test_get_file_extension_lowercase_with_dot() -> None:
    """扩展名小写且含点。"""

    assert get_file_extension(Path("SHOW.MKV")) == ".mkv"
    assert get_file_extension(Path("/a/b/c.mp4")) == ".mp4"
    assert get_file_extension(Path("no_ext")) == ""


def test_is_video_file_whitelist() -> None:
    """白名单内的扩展名识别为视频。"""

    for ext in VIDEO_EXTENSIONS:
        assert is_video_file(Path(f"sample{ext}")) is True
    assert is_video_file(Path("x.txt")) is False
    assert is_video_file(Path("x")) is False
