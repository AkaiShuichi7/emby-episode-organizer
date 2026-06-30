"""命名模板测试。

验证 ``filename_gen`` 的视频、NFO、封面与季目录命名约定。
"""

from app.utils.naming import (
    NamingContext,
    generate_nfo_filename,
    generate_season_folder,
    generate_thumb_filename,
    generate_video_filename,
)


def test_generate_video_filename_uses_sanitized_names() -> None:
    """系列名与标题先清洗，再套入视频模板。"""

    ctx = NamingContext("三叉戟", 2, 3, "AAA", ".mp4")

    assert generate_video_filename(ctx) == "三叉戟 - S02E03 - AAA.mp4"


def test_generate_nfo_filename_uses_default_template() -> None:
    """NFO 文件名遵循固定模板。"""

    ctx = NamingContext("三叉戟", 2, 3, "AAA", ".mp4")

    assert generate_nfo_filename(ctx) == "三叉戟 - S02E03 - AAA.nfo"


def test_generate_thumb_filename_uses_default_template() -> None:
    """封面文件名遵循固定模板。"""

    ctx = NamingContext("三叉戟", 2, 3, "AAA", ".mp4")

    assert generate_thumb_filename(ctx) == "三叉戟 - S02E03 - AAA-thumb.jpg"


def test_generate_season_folder_uses_two_digits() -> None:
    """季目录默认补零到两位。"""

    assert generate_season_folder(1) == "Season 01"
    assert generate_season_folder(15) == "Season 15"


def test_generate_video_filename_keeps_three_digit_episode() -> None:
    """集数大于 99 时不截断。"""

    ctx = NamingContext("X", 1, 100, "T", ".mp4")

    assert generate_video_filename(ctx) == "X - S01E100 - T.mp4"


def test_generate_video_filename_sanitizes_special_chars() -> None:
    """系列名与标题中的非法字符会被清洗。"""

    ctx = NamingContext("a:b/c", 1, 1, "q?x*", ".mp4")

    assert generate_video_filename(ctx) == "a_b_c - S01E01 - q_x_.mp4"
