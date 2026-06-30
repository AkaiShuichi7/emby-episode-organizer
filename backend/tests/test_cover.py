"""封面下载器测试。

覆盖：成功下载、20MB 截断、错误 Content-Type、超时、file:// scheme、
LAN IP scheme 允许、Pillow 校验失败清理。
"""

from __future__ import annotations

import io
from pathlib import Path

import httpx
import pytest
import respx
from PIL import Image

from app.services.cover import (
    ALLOWED_CONTENT_TYPES,
    DOWNLOAD_TIMEOUT,
    MAX_COVER_SIZE,
    CoverInvalidContentTypeError,
    CoverInvalidURLError,
    CoverResult,
    CoverTimeoutError,
    CoverTooLargeError,
    download_cover,
)


def _make_jpeg_bytes(width: int = 8, height: int = 8) -> bytes:
    """生成有效 JPEG 字节用于模拟图片下载。"""
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(255, 0, 0)).save(buf, format="JPEG")
    return buf.getvalue()


def _make_png_bytes(width: int = 8, height: int = 8) -> bytes:
    """生成有效 PNG 字节用于模拟图片下载。"""
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(0, 255, 0)).save(buf, format="PNG")
    return buf.getvalue()


async def test_download_jpeg_success(tmp_path: Path) -> None:
    """成功下载 jpg 返回 CoverResult，文件落盘。"""
    jpeg = _make_jpeg_bytes()
    dest = tmp_path / "cover.jpg"

    with respx.mock(base_url="https://cdn.example.com") as mock:
        route = mock.get("/ep1.jpg").respond(
            200, content=jpeg, headers={"Content-Type": "image/jpeg"}
        )

        async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT) as client:
            result = await download_cover("https://cdn.example.com/ep1.jpg", dest, client=client)

    assert route.called
    assert isinstance(result, CoverResult)
    assert result.path == dest
    assert result.content_type == "image/jpeg"
    assert result.size == len(jpeg)
    assert dest.read_bytes() == jpeg


async def test_download_png_success(tmp_path: Path) -> None:
    """成功下载 png 返回 CoverResult。"""
    png = _make_png_bytes()
    dest = tmp_path / "cover.png"

    with respx.mock(base_url="https://cdn.example.com") as mock:
        mock.get("/ep1.png").respond(
            200, content=png, headers={"Content-Type": "image/png"}
        )

        async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT) as client:
            result = await download_cover("https://cdn.example.com/ep1.png", dest, client=client)

    assert result.content_type == "image/png"
    assert result.size == len(png)
    assert dest.read_bytes() == png


async def test_too_large_raises_and_cleans_partial(tmp_path: Path) -> None:
    """响应超过 MAX_COVER_SIZE 抛 CoverTooLargeError 并清理不完整文件。"""
    # 实际流式发送 25MB，确保累计检测能触发
    big = b"\x00" * (MAX_COVER_SIZE + 1024 * 1024)
    dest = tmp_path / "big.jpg"

    with respx.mock(base_url="https://cdn.example.com") as mock:
        mock.get("/huge.jpg").respond(
            200, content=big, headers={"Content-Type": "image/jpeg"}
        )

        async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT) as client:
            with pytest.raises(CoverTooLargeError):
                await download_cover(
                    "https://cdn.example.com/huge.jpg", dest, client=client
                )

    assert not dest.exists(), "超出大小限制时必须清理不完整的目标文件"


async def test_html_content_type_rejected(tmp_path: Path) -> None:
    """Content-Type 非白名单抛 CoverInvalidContentTypeError。"""
    dest = tmp_path / "bad.jpg"

    with respx.mock(base_url="https://cdn.example.com") as mock:
        mock.get("/page").respond(200, content=b"<html>oops</html>", headers={"Content-Type": "text/html"})

        async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT) as client:
            with pytest.raises(CoverInvalidContentTypeError):
                await download_cover("https://cdn.example.com/page", dest, client=client)

    assert not dest.exists()


async def test_octet_stream_content_type_rejected(tmp_path: Path) -> None:
    """Content-Type 缺失/通用 octet-stream 不在白名单必须拒。"""
    dest = tmp_path / "unknown.bin"

    with respx.mock(base_url="https://cdn.example.com") as mock:
        mock.get("/x").respond(200, content=b"junk", headers={"Content-Type": "application/octet-stream"})

        async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT) as client:
            with pytest.raises(CoverInvalidContentTypeError):
                await download_cover("https://cdn.example.com/x", dest, client=client)


async def test_timeout_raises_cover_timeout(tmp_path: Path) -> None:
    """httpx 抛 TimeoutException 时，封装为 CoverTimeoutError 并清理文件。"""
    dest = tmp_path / "slow.jpg"

    with respx.mock(base_url="https://cdn.example.com") as mock:
        # 直接让 respx 抛 TimeoutException，覆盖 httpx 超时分支
        mock.get("/slow.jpg").mock(side_effect=httpx.TimeoutException("simulated timeout"))

        async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT) as client:
            with pytest.raises(CoverTimeoutError):
                await download_cover("https://cdn.example.com/slow.jpg", dest, client=client)

    assert not dest.exists()


async def test_file_scheme_rejected(tmp_path: Path) -> None:
    """file:// scheme 不允许，抛 CoverInvalidURLError。"""
    dest = tmp_path / "leak.jpg"

    with pytest.raises(CoverInvalidURLError):
        await download_cover("file:///etc/passwd", dest)


async def test_ftp_scheme_rejected(tmp_path: Path) -> None:
    """ftp:// scheme 不允许，抛 CoverInvalidURLError。"""
    dest = tmp_path / "leak.jpg"

    with pytest.raises(CoverInvalidURLError):
        await download_cover("ftp://example.com/cover.jpg", dest)


async def test_lan_ip_allowed(tmp_path: Path) -> None:
    """LAN IP (http://192.168.x.x) scheme 校验通过。"""
    jpeg = _make_jpeg_bytes()
    dest = tmp_path / "lan.jpg"

    with respx.mock(base_url="http://192.168.1.10:8096") as mock:
        mock.get("/cover.jpg").respond(
            200, content=jpeg, headers={"Content-Type": "image/jpeg"}
        )

        async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT) as client:
            result = await download_cover("http://192.168.1.10:8096/cover.jpg", dest, client=client)

    assert result.content_type == "image/jpeg"
    assert dest.read_bytes() == jpeg


async def test_corrupted_image_cleans_up(tmp_path: Path) -> None:
    """JPEG magic 但内容损坏，Pillow verify 失败抛 CoverInvalidContentTypeError。"""
    # JPG magic + 随机字节：header 合法但图像结构损坏
    corrupted = b"\xff\xd8\xff\xe0" + b"not a real jpeg" * 4
    dest = tmp_path / "corrupt.jpg"

    with respx.mock(base_url="https://cdn.example.com") as mock:
        mock.get("/bad.jpg").respond(
            200, content=corrupted, headers={"Content-Type": "image/jpeg"}
        )

        async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT) as client:
            with pytest.raises(CoverInvalidContentTypeError):
                await download_cover("https://cdn.example.com/bad.jpg", dest, client=client)

    assert not dest.exists()


async def test_allowed_content_types_constant() -> None:
    """白名单包含 jpeg/png/webp。"""
    assert {"image/jpeg", "image/png", "image/webp"} == ALLOWED_CONTENT_TYPES


async def test_no_http_request_made_for_invalid_scheme(tmp_path: Path) -> None:
    """scheme 非法时不应该发出任何网络请求。"""
    dest = tmp_path / "x.jpg"

    with respx.mock(assert_all_called=False) as mock:
        with pytest.raises(CoverInvalidURLError):
            await download_cover("data:image/png;base64,iVBORw0KGgo=", dest)
        assert not mock.calls, "scheme 校验失败时不应触发网络"
