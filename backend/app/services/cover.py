"""封面图下载器。

负责从给定的 http/https URL 下载剧集封面图，写入目标路径。下载过程严格
校验 scheme、Content-Type、文件大小，并用 Pillow 二次确认是合法图片。

设计要点：
- 仅接受 http/https scheme（拒 file/ftp/data 等），防止读取本地文件
  或被 data URL 注入。
- 白名单 Content-Type 提前校验，避免写入 HTML/JSON 等错误响应。
- 流式写入并在累计字节超限时立即中止并清理，避免磁盘被打爆。
- Pillow ``Image.verify()`` 不解码像素，只验证结构，能在毫秒级抓坏图。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import NamedTuple

import httpx
from PIL import Image, UnidentifiedImageError

# 白名单 Content-Type：Emby/Kodi 封面常见三种格式
ALLOWED_CONTENT_TYPES: frozenset[str] = frozenset({"image/jpeg", "image/png", "image/webp"})

# 20MB 单文件硬上限，防止恶意或异常响应灌满磁盘
MAX_COVER_SIZE: int = 20 * 1024 * 1024

# 下载整体超时（连接 + 读取）
DOWNLOAD_TIMEOUT: float = 10.0

# 默认下载缓冲大小（每次从响应流读取的字节数）
_CHUNK_SIZE: int = 64 * 1024

logger = logging.getLogger(__name__)


class CoverResult(NamedTuple):
    """封面下载成功结果。

    Attributes:
        path: 写入的目标文件路径。
        content_type: 服务器返回的 Content-Type（已校验在白名单内）。
        size: 实际写入字节数。
    """

    path: Path
    content_type: str
    size: int


class CoverTooLargeError(Exception):
    """响应体超过 MAX_COVER_SIZE 时抛出。"""


class CoverTimeoutError(Exception):
    """下载整体超时时抛出。"""


class CoverInvalidURLError(Exception):
    """URL scheme 不在 http/https 白名单时抛出。"""


class CoverInvalidContentTypeError(Exception):
    """Content-Type 不在白名单、或 Pillow 校验图片失败时抛出。"""


def _validate_scheme(url: str) -> None:
    """仅允许 http/https scheme，其它（file/ftp/data 等）一律拒绝。"""
    # ponytail: 不引入 yarl，stdlib str.split 足够，避免为这一个校验多拉依赖
    scheme = url.split(":", 1)[0].lower() if ":" in url else ""
    if scheme not in {"http", "https"}:
        raise CoverInvalidURLError(f"不支持的 URL scheme: {scheme!r}（仅允许 http/https）")


def _cleanup_partial(dest: Path) -> None:
    """下载失败时清理可能残留的不完整目标文件。"""
    try:
        dest.unlink(missing_ok=True)
    except OSError as exc:  # pragma: no cover - 极端磁盘错误
        logger.warning("清理不完整封面文件失败: path=%s err=%s", dest, exc)


def _verify_image(path: Path) -> None:
    """用 Pillow 二次校验文件是合法图片。

    ``verify()`` 不解码像素，速度快；任何格式错误都抛出
    ``UnidentifiedImageError`` 或 ``OSError``/``SyntaxError``。
    """
    with Image.open(path) as img:
        img.verify()


async def download_cover(
    url: str,
    dest: Path,
    *,
    client: httpx.AsyncClient | None = None,
) -> CoverResult:
    """下载封面图到 ``dest``。

    Args:
        url: 远程封面 URL，必须是 http/https。
        dest: 本地落盘路径，父目录需已存在。
        client: 可选注入的 httpx 客户端（测试用）。生产路径内部创建。

    Returns:
        ``CoverResult``，含写入路径、Content-Type、字节数。

    Raises:
        CoverInvalidURLError: scheme 校验失败。
        CoverInvalidContentTypeError: Content-Type 不在白名单或图片结构损坏。
        CoverTooLargeError: 响应体超过 ``MAX_COVER_SIZE``。
        CoverTimeoutError: 下载整体超过 ``DOWNLOAD_TIMEOUT``。
    """
    _validate_scheme(url)

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT)
    assert client is not None  # for type checker

    try:
        try:
            async with client.stream("GET", url, timeout=DOWNLOAD_TIMEOUT) as response:
                content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
                if content_type not in ALLOWED_CONTENT_TYPES:
                    raise CoverInvalidContentTypeError(
                        f"Content-Type 不在白名单: {content_type!r}"
                    )

                written = 0
                with dest.open("wb") as fh:
                    async for chunk in response.aiter_bytes(_CHUNK_SIZE):
                        if not chunk:
                            continue
                        written += len(chunk)
                        if written > MAX_COVER_SIZE:
                            fh.close()
                            _cleanup_partial(dest)
                            raise CoverTooLargeError(
                                f"封面超过 {MAX_COVER_SIZE} 字节上限"
                            )
                        fh.write(chunk)

        except httpx.TimeoutException as exc:
            _cleanup_partial(dest)
            raise CoverTimeoutError(f"下载封面超时: {exc}") from exc
        except httpx.TransportError as exc:
            _cleanup_partial(dest)
            raise CoverTimeoutError(f"下载封面传输错误: {exc}") from exc
        except CoverInvalidContentTypeError:
            _cleanup_partial(dest)
            raise
        except CoverTooLargeError:
            raise

        # 字节级校验通过后，再用 Pillow 确认是合法图片
        try:
            _verify_image(dest)
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
            _cleanup_partial(dest)
            raise CoverInvalidContentTypeError(f"Pillow 校验图片失败: {exc}") from exc

        size = dest.stat().st_size
        logger.info(
            "封面下载成功: url=%s path=%s content_type=%s size=%d",
            url,
            dest,
            content_type,
            size,
        )
        return CoverResult(path=dest, content_type=content_type, size=size)
    finally:
        if owns_client:
            await client.aclose()
