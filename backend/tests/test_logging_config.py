"""日志配置测试。"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest

from app.logging_config import JsonFormatter, setup_logging


@pytest.fixture(autouse=True)
def restore_root_logger() -> Iterator[None]:
    """测试结束后还原 root logger，避免 handler 污染其它用例。"""
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level

    yield

    for handler in root.handlers[:]:
        handler.close()
    root.handlers = original_handlers
    root.setLevel(original_level)


def test_setup_logging_creates_json_log_file(tmp_path: Path) -> None:
    """首次写日志时创建目录和 JSON 日志文件。"""
    setup_logging(tmp_path)

    logging.getLogger("测试日志").info("应用启动")

    log_file = tmp_path / "app.log"
    assert log_file.exists()

    first_line = log_file.read_text(encoding="utf-8").splitlines()[0]
    payload = cast(dict[str, object], json.loads(first_line))

    assert payload["msg"] == "应用启动"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "测试日志"
    assert {"ts", "level", "logger", "msg"} <= payload.keys()


def test_setup_logging_is_idempotent(tmp_path: Path) -> None:
    """重复初始化不叠加 handler。"""
    setup_logging(tmp_path)
    first_handlers = list(logging.getLogger().handlers)

    setup_logging(tmp_path)

    root = logging.getLogger()
    assert len(root.handlers) == 2
    assert len({id(handler) for handler in root.handlers}) == 2
    assert len(first_handlers) == 2


def test_json_formatter_outputs_required_keys() -> None:
    """JSON 格式化器输出固定字段。"""
    record = logging.LogRecord(
        name="测试日志",
        level=logging.INFO,
        pathname=__file__,
        lineno=123,
        msg="数据库初始化完成",
        args=(),
        exc_info=None,
        func="test_json_formatter_outputs_required_keys",
    )

    payload = cast(dict[str, object], json.loads(JsonFormatter().format(record)))

    assert payload["msg"] == "数据库初始化完成"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "测试日志"
    assert payload["func"] == "test_json_formatter_outputs_required_keys"
    assert payload["line"] == 123
