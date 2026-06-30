"""Kodi episode NFO 构建/解析器测试。

验证最小/完整 NFO 序列化、空字段省略、多 actor、XML 转义、round-trip。
"""

from __future__ import annotations

from app.services.nfo import Actor, NFOData, build_nfo_xml, parse_nfo_xml

# XML 声明头 (ElementTree 默认输出格式)
XML_DECL = "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"


def test_minimal_nfo_contains_only_required_tags() -> None:
    """最小 NFO 只含 title/season/episode 三个标签。"""
    data = NFOData(title="第一集", season=1, episode=1)
    xml = build_nfo_xml(data)

    assert "<title>第一集</title>" in xml
    assert "<season>1</season>" in xml
    assert "<episode>1</episode>" in xml
    assert "<plot>" not in xml
    assert "<genre>" not in xml
    assert "<actor>" not in xml


def test_full_nfo_includes_all_populated_fields() -> None:
    """完整 NFO 含 actor/genre/tag/director/studio/rating/plot/premiered/year。"""
    data = NFOData(
        title="试播集",
        season=1,
        episode=1,
        plot="一段剧情简介。",
        premiered="2024-01-15",
        year=2024,
        genre=["剧情", "科幻"],
        tag=["经典"],
        actor=[Actor(name="张三", role="主角")],
        director=["李四"],
        studio="某工作室",
        rating=8.5,
    )
    xml = build_nfo_xml(data)

    assert "<title>试播集</title>" in xml
    assert "<plot>一段剧情简介。</plot>" in xml
    assert "<premiered>2024-01-15</premiered>" in xml
    assert "<year>2024</year>" in xml
    assert "<genre>剧情</genre>" in xml
    assert "<genre>科幻</genre>" in xml
    assert "<tag>经典</tag>" in xml
    assert "<director>李四</director>" in xml
    assert "<studio>某工作室</studio>" in xml
    assert "<rating>8.5</rating>" in xml
    assert "<actor>" in xml
    assert "<name>张三</name>" in xml
    assert "<role>主角</role>" in xml


def test_empty_plot_omitted_from_xml() -> None:
    """空 plot 不生成 <plot> 标签。"""
    data = NFOData(title="x", season=1, episode=1, plot=None)
    xml = build_nfo_xml(data)
    assert "<plot>" not in xml


def test_empty_genre_list_omitted_from_xml() -> None:
    """空 genre 列表不生成 <genre> 标签。"""
    data = NFOData(title="x", season=1, episode=1, genre=[])
    xml = build_nfo_xml(data)
    assert "<genre>" not in xml


def test_multiple_actors_produce_multiple_actor_tags() -> None:
    """2 个 actor → 2 个 <actor> 标签。"""
    data = NFOData(
        title="x",
        season=1,
        episode=1,
        actor=[
            Actor(name="张三", role="主角"),
            Actor(name="王五", role="配角"),
        ],
    )
    xml = build_nfo_xml(data)

    assert xml.count("<actor>") == 2
    assert xml.count("</actor>") == 2
    assert "<name>张三</name>" in xml
    assert "<name>王五</name>" in xml
    assert "<role>主角</role>" in xml
    assert "<role>配角</role>" in xml


def test_actor_without_role_omits_role_tag() -> None:
    """Actor.role=None 时不生成 <role> 标签。"""
    data = NFOData(
        title="x",
        season=1,
        episode=1,
        actor=[Actor(name="路人甲", role=None)],
    )
    xml = build_nfo_xml(data)

    assert "<name>路人甲</name>" in xml
    assert "<role>" not in xml


def test_output_starts_with_xml_declaration() -> None:
    """输出以 XML 声明头开头。"""
    data = NFOData(title="x", season=1, episode=1)
    xml = build_nfo_xml(data)

    assert xml.startswith(XML_DECL)


def test_root_element_is_episodedetails() -> None:
    """根元素是 <episodedetails>。"""
    data = NFOData(title="x", season=1, episode=1)
    xml = build_nfo_xml(data)

    assert "<episodedetails>" in xml
    assert "</episodedetails>" in xml


def test_round_trip_minimal() -> None:
    """最小 NFO build → parse 还原相等。"""
    data = NFOData(title="第一集", season=2, episode=3)
    parsed = parse_nfo_xml(build_nfo_xml(data))
    assert parsed == data


def test_round_trip_full() -> None:
    """完整 NFO build → parse 还原相等 (含中文/小数)。"""
    data = NFOData(
        title="试播集",
        season=1,
        episode=1,
        plot="一段剧情简介。",
        premiered="2024-01-15",
        year=2024,
        genre=["剧情", "科幻"],
        tag=["经典", "必看"],
        actor=[Actor(name="张三", role="主角"), Actor(name="王五", role=None)],
        director=["李四", "赵六"],
        studio="某工作室",
        rating=8.5,
    )
    parsed = parse_nfo_xml(build_nfo_xml(data))
    assert parsed == data


def test_xml_escape_ampersand_in_title() -> None:
    """title='AT&T' build 后 parse 还原 'AT&T'。"""
    data = NFOData(title="AT&T", season=1, episode=1)
    xml = build_nfo_xml(data)

    # 序列化时 '&' 必须转义为 '&amp;'
    assert "&amp;" in xml
    assert "<title>AT&amp;T</title>" in xml

    # 解析时还原
    parsed = parse_nfo_xml(xml)
    assert parsed.title == "AT&T"


def test_xml_escape_angle_brackets_in_title() -> None:
    """title='<script>' 正确转义为 &lt;script&gt;。"""
    data = NFOData(title="<script>", season=1, episode=1)
    xml = build_nfo_xml(data)

    assert "&lt;script&gt;" in xml
    # 不应出现原始未转义的 <script>
    assert "<title><script>" not in xml
    assert "<title>&lt;script&gt;</title>" in xml

    parsed = parse_nfo_xml(xml)
    assert parsed.title == "<script>"


def test_parse_minimal_xml_string() -> None:
    """直接解析 XML 字符串构造 NFOData。"""
    xml_str = (
        f"{XML_DECL}\n"
        "<episodedetails>"
        "<title>直接解析</title>"
        "<season>5</season>"
        "<episode>12</episode>"
        "</episodedetails>"
    )
    parsed = parse_nfo_xml(xml_str)

    assert parsed.title == "直接解析"
    assert parsed.season == 5
    assert parsed.episode == 12
    assert parsed.plot is None
    assert parsed.genre == []


def test_parse_full_xml_string_with_actors() -> None:
    """解析含多 actor/genre/director 的 XML。"""
    xml_str = (
        f"{XML_DECL}\n"
        "<episodedetails>"
        "<title>剧集</title>"
        "<season>1</season>"
        "<episode>1</episode>"
        "<genre>剧情</genre>"
        "<genre>科幻</genre>"
        "<director>李四</director>"
        "<actor><name>张三</name><role>主角</role></actor>"
        "<actor><name>王五</name></actor>"
        "</episodedetails>"
    )
    parsed = parse_nfo_xml(xml_str)

    assert parsed.title == "剧集"
    assert parsed.genre == ["剧情", "科幻"]
    assert parsed.director == ["李四"]
    assert parsed.actor == [
        Actor(name="张三", role="主角"),
        Actor(name="王五", role=None),
    ]


def test_parse_preserves_unicode() -> None:
    """解析保留中文字符。"""
    xml_str = (
        f"{XML_DECL}\n"
        "<episodedetails>"
        "<title>中文标题</title>"
        "<season>1</season>"
        "<episode>1</episode>"
        "<plot>剧情简介</plot>"
        "</episodedetails>"
    )
    parsed = parse_nfo_xml(xml_str)

    assert parsed.title == "中文标题"
    assert parsed.plot == "剧情简介"
