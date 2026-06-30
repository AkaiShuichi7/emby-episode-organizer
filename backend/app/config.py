"""应用全局配置。

通过 pydantic-settings 从环境变量 / .env 加载配置，集中管理数据库、日志、
路径白名单与 Emby 默认地址等运行参数。
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """运行时配置项。

    属性:
        database_url: SQLAlchemy 异步数据库连接串。
        log_dir: 操作日志输出目录。
        allowed_browse_roots: 允许浏览 / 操作的根目录白名单（路径安全边界）。
        emby_default_url: Emby 服务器默认地址，供前端预填。
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    log_dir: Path = Path("./data/logs")
    allowed_browse_roots: list[Path] = [Path("/data")]
    emby_default_url: str = "http://localhost:8096"


settings = Settings()
"""全局配置单例，生命周期与进程一致。"""
