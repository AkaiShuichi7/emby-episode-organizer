"""命名模板与文件名生成。

集中维护视频、NFO、封面和季目录的命名规则，供整理流程复用。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.utils.filename import sanitize_filename, sanitize_series_name

#: 季目录模板。
SEASON_FOLDER_TEMPLATE = "Season {season:02d}"

#: 视频文件模板。
VIDEO_TEMPLATE = "{series} - S{season:02d}E{episode:02d} - {title}{ext}"

#: NFO 文件模板。
NFO_TEMPLATE = "{series} - S{season:02d}E{episode:02d} - {title}.nfo"

#: 封面缩略图模板。
THUMB_TEMPLATE = "{series} - S{season:02d}E{episode:02d} - {title}-thumb.jpg"


@dataclass(frozen=True, slots=True)
class NamingContext:
    """命名所需上下文。

    属性:
        series: 剧集名。
        season: 季号。
        episode: 集号。
        title: 集标题。
        ext: 视频扩展名，包含前导 ``.``。
    """

    series: str
    season: int
    episode: int
    title: str
    ext: str


def generate_video_filename(ctx: NamingContext) -> str:
    """生成视频文件名。

    系列名先走 :func:`app.utils.filename.sanitize_series_name`，标题先走
    :func:`app.utils.filename.sanitize_filename`，再套用视频模板。

    参数:
        ctx: 命名上下文。

    返回:
        视频文件名。
    """

    return VIDEO_TEMPLATE.format(
        series=sanitize_series_name(ctx.series),
        season=ctx.season,
        episode=ctx.episode,
        title=sanitize_filename(ctx.title),
        ext=ctx.ext,
    )


def generate_nfo_filename(ctx: NamingContext) -> str:
    """生成 NFO 文件名。

    参数:
        ctx: 命名上下文。

    返回:
        NFO 文件名。
    """

    return NFO_TEMPLATE.format(
        series=ctx.series,
        season=ctx.season,
        episode=ctx.episode,
        title=ctx.title,
    )


def generate_thumb_filename(ctx: NamingContext) -> str:
    """生成封面缩略图文件名。

    参数:
        ctx: 命名上下文。

    返回:
        封面缩略图文件名。
    """

    return THUMB_TEMPLATE.format(
        series=ctx.series,
        season=ctx.season,
        episode=ctx.episode,
        title=ctx.title,
    )


def generate_season_folder(season: int) -> str:
    """生成季目录名。

    参数:
        season: 季号。

    返回:
        季目录名。
    """

    return SEASON_FOLDER_TEMPLATE.format(season=season)
