# Learnings: Emby Episode Organizer

## 项目约定
- 目录: `/Users/akaishuichi/Developer/Other/python/emby-episode-organizer`
- 不是 git 仓库（待 T1 初始化）
- TDD 工作流: pytest + vitest
- 镜像: Docker Hub `akaishuichiw/emby-episode-organizer`
- 端口: 8899
- 用户语言: 简体中文, caveman mode
- 注释中文, 代码英文
- Git 提交: Conventional Commits, 中文描述

## 命名规则（铁律）
- 视频: `{series} - S{season:02d}E{episode:02d} - {title}{ext}`
- NFO: `{series} - S{season:02d}E{episode:02d} - {title}.nfo`
- 封面: `{series} - S{season:02d}E{episode:02d} - {title}-thumb.jpg`
- 季目录: `Season {season:02d}`

## 路径概念
- stagingPath: 整理缓存, **不是** Emby 媒体库
- targetPath: Emby 实际挂载目录
- 最新集数必须 Emby API 取, **不**扫描 stagingPath

## 关键技术决策
- Python 3.12+ / xml.etree.ElementTree (stdlib) / stdlib logging + JSON
- Vue 3 + Naive UI + Pinia / openapi-typescript 自动生成
- Ruff + mypy / ESLint + Prettier
- 容器 UID 1000 非 root
- 大文件移动: `.tmp` + rename 原子化
- 并发冲突: DB unique constraint on (series_id, season, episode)
- API Key 存储 SQLite 明文, 响应 mask `xxxx****`
- 路径安全: safe_resolve 集中校验, 拒 symlink 出 allow-list

## 后端骨架记录
- FastAPI 入口保持最小: `app.main:app` + `/health`
- 测试用 `httpx.AsyncClient` + `ASGITransport`，不引入 `TestClient`
- `.python-version` 固定 3.12，虚拟环境也要用 `python3.12` 创建
- Ruff 配置单独放 `ruff.toml`，pyproject 只留 `tool.ruff` 入口

## 前端骨架记录
- Vite 5 + Vue 3 + Naive UI + Pinia 骨架可直接用 `vite.config.ts` + `vitest.config.ts` 双配置
- Naive UI 当前安装包没有 `dist/preset.css` 实文件，构建时可用 Vite alias 做兼容
- vitest 跑 `.vue` 需要 `@vitejs/plugin-vue`，否则会卡在 SFC 解析
- ESLint `--ignore-path .gitignore` 会要求 frontend 目录自己也有 `.gitignore`

## T4 数据库模型
- 异步 SQLAlchemy 需 `sqlalchemy[asyncio]` extra (拉 greenlet)，否则运行报 "greenlet library is required"
- mypy strict 下用 `class Base(DeclarativeBase)` 而非 `declarative_base()`（后者返回 Any，子类化报错）
- mypy strict 下 JSON 列须写 `Mapped[dict[str, Any] | None]`，裸 dict 报 type-arg
- ruff UP042: 枚举用 `enum.StrEnum`（Py3.12）而非 `(str, enum.Enum)`
- init_db(target_engine) 可注入引擎，测试用 `sqlite+aiosqlite:///:memory:`
- init_db.py 须 import models 触发表注册到 Base.metadata（加 noqa: F401）
