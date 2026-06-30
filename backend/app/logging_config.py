"""应用日志配置。"""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import override


class JsonFormatter(logging.Formatter):
    """把日志记录格式化为单行 JSON。"""

    @override
    def format(self, record: logging.LogRecord) -> str:
        """输出包含固定字段的 JSON 字符串。"""
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
        }
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(log_dir: Path, level: str = "INFO") -> None:
    """配置 root logger，输出到控制台和滚动文件。"""
    log_dir.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        handler.close()
    root_logger.handlers.clear()

    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    formatter = JsonFormatter()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
