"""Kodi episode NFO 构建/解析器。

基于 Kodi v12 episode NFO 格式，使用 stdlib xml.etree.ElementTree 完成 XML
序列化与反序列化。本模块**只构造字符串，不写文件**——文件落盘由上层调用
（命名模板、Emby 媒体库写入）负责。

设计要点：
- 空字段不生成 XML 标签，解析时缺失标签对应回 None / 空列表。
- XML 特殊字符（&、<、>）由 ElementTree 自动转义，round-trip 还原。
- 根元素固定为 ``<episodedetails>``，Kodi/Emby 扫描单集 NFO 时识别。
"""

from __future__ import annotations

from xml.etree import ElementTree as ET

from pydantic import BaseModel, Field

# Kodi 习惯：根元素名固定为 episodedetails
_ROOT_TAG = "episodedetails"

# XML 声明头。ElementTree 默认不带 standalone='yes'，手动拼装确保兼容
# Kodi/Emby 的解析器对 standalone 属性的要求。
_XML_DECL = "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"


class Actor(BaseModel):
    """演员条目。

    Attributes:
        name: 演员姓名（必填）。
        role: 饰演角色，可空。
    """

    name: str
    role: str | None = None


class NFOData(BaseModel):
    """Kodi 单集 NFO 数据模型。

    字段命名对齐 Kodi v12 episode NFO schema（title/season/episode/...）。
    列表字段默认空列表，可选字段默认 None，方便上层按需填充。
    """

    # 必填字段
    title: str
    season: int
    episode: int
    # 文本字段
    plot: str | None = None
    premiered: str | None = None
    year: int | None = None
    studio: str | None = None
    rating: float | None = None
    # 列表字段
    genre: list[str] = Field(default_factory=list)
    tag: list[str] = Field(default_factory=list)
    director: list[str] = Field(default_factory=list)
    actor: list[Actor] = Field(default_factory=list)


def _maybe_add(parent: ET.Element, tag: str, value: object) -> None:
    """当 value 非空时追加文本子元素。

    ponytail: 集中处理"空就不生成标签"语义，避免 build_nfo_xml 里散落判断。
    """

    if value is None:
        return
    if isinstance(value, str) and value == "":
        return
    # 列表由调用方逐项处理；这里只处理标量
    if isinstance(value, (list, tuple)):
        return
    element = ET.SubElement(parent, tag)
    element.text = str(value)


def build_nfo_xml(data: NFOData) -> str:
    """将 NFOData 序列化为 Kodi episode NFO XML 字符串。

    Args:
        data: 待序列化的 NFO 数据。

    Returns:
        以 XML 声明头开头的完整 XML 字符串，含 ``<episodedetails>`` 根元素。

    Notes:
        - 空字段（None / 空串 / 空列表）不生成对应 XML 标签。
        - 多值字段（genre / tag / director / actor）展开为多个同名元素。
        - 不负责写文件，仅返回字符串。
    """

    root = ET.Element(_ROOT_TAG)

    # 标量字段
    _maybe_add(root, "title", data.title)
    _maybe_add(root, "season", data.season)
    _maybe_add(root, "episode", data.episode)
    _maybe_add(root, "plot", data.plot)
    _maybe_add(root, "premiered", data.premiered)
    _maybe_add(root, "year", data.year)
    _maybe_add(root, "studio", data.studio)
    _maybe_add(root, "rating", data.rating)

    # 列表字段：空列表自然不进入循环
    for value in data.genre:
        _maybe_add(root, "genre", value)
    for value in data.tag:
        _maybe_add(root, "tag", value)
    for value in data.director:
        _maybe_add(root, "director", value)

    # actor 展开为带 name/role 子元素的结构
    for actor in data.actor:
        actor_el = ET.SubElement(root, "actor")
        _maybe_add(actor_el, "name", actor.name)
        _maybe_add(actor_el, "role", actor.role)

    # encoding='unicode' 返回 str，不带 XML 声明；手动拼接声明头。
    body = ET.tostring(root, encoding="unicode")
    return f"{_XML_DECL}\n{body}"


def _text_or_none(element: ET.Element, tag: str) -> str | None:
    """读取子元素文本；缺失或空文本返回 None。"""

    child = element.find(tag)
    if child is None or child.text is None:
        return None
    return child.text


def _int_or_none(element: ET.Element, tag: str) -> int | None:
    """读取子元素整数文本；缺失或解析失败返回 None。"""

    raw = _text_or_none(element, tag)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        # ponytail: 防御解析异常，避免脏 NFO 直接拖垮上层
        return None


def _float_or_none(element: ET.Element, tag: str) -> float | None:
    """读取子元素浮点文本；缺失或解析失败返回 None。"""

    raw = _text_or_none(element, tag)
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _list_of_text(element: ET.Element, tag: str) -> list[str]:
    """读取同名子元素文本列表；缺失或为空返回空列表。"""

    return [child.text for child in element.findall(tag) if child.text]


def parse_nfo_xml(xml_str: str) -> NFOData:
    """将 Kodi episode NFO XML 字符串解析回 NFOData。

    Args:
        xml_str: 含 ``<episodedetails>`` 根元素的 XML 字符串。

    Returns:
        反序列化得到的 NFOData；缺失字段回退为 None / 空列表。

    Raises:
        ValueError: 根元素不是 ``<episodedetails>``，或缺少必填字段。
    """

    root = ET.fromstring(xml_str)
    if root.tag != _ROOT_TAG:
        raise ValueError(f"NFO 根元素必须是 <{_ROOT_TAG}>，收到 <{root.tag}>")

    title = _text_or_none(root, "title")
    season = _int_or_none(root, "season")
    episode = _int_or_none(root, "episode")
    if title is None or season is None or episode is None:
        raise ValueError("NFO 缺少必填字段 title/season/episode")

    actors: list[Actor] = []
    for actor_el in root.findall("actor"):
        name = _text_or_none(actor_el, "name")
        if name is None:
            continue
        actors.append(Actor(name=name, role=_text_or_none(actor_el, "role")))

    return NFOData(
        title=title,
        season=season,
        episode=episode,
        plot=_text_or_none(root, "plot"),
        premiered=_text_or_none(root, "premiered"),
        year=_int_or_none(root, "year"),
        studio=_text_or_none(root, "studio"),
        rating=_float_or_none(root, "rating"),
        genre=_list_of_text(root, "genre"),
        tag=_list_of_text(root, "tag"),
        director=_list_of_text(root, "director"),
        actor=actors,
    )


if __name__ == "__main__":
    # ponytail: 最小自检，验证 build → parse round-trip 能跑通。
    sample = NFOData(
        title="自检集",
        season=1,
        episode=1,
        plot="剧情",
        genre=["剧情"],
        actor=[Actor(name="测试", role="主角")],
    )
    xml = build_nfo_xml(sample)
    assert "<title>自检集</title>" in xml
    assert parse_nfo_xml(xml) == sample
    print(xml)
