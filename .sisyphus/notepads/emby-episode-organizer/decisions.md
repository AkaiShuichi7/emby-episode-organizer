# Decisions Log

## D1: 镜像仓库 = Docker Hub (非 GHCR)
- 用户: AkaiShuichi7, Docker Hub 用户名小写化: `akaishuichiw`
- 镜像名: `akaishuichiw/emby-episode-organizer`
- 原因: 用户偏好 Docker Hub 生态

## D2: 测试策略 = TDD
- pytest + vitest, RED→GREEN→REFACTOR
- 原因: 用户选, 提高代码质量

## D3: 任务状态机 = 完整 7 状态
- draft, staged, nfo_edited, ready_to_commit, committed, failed, cancelled
- v1 简化使用: staged, committed, failed
- 但后端模型保留全部枚举值

## D4: 大文件移动 = 异步 + .tmp + rename
- BackgroundTasks 异步执行
- 复制到 .tmp → 验证 size → rename → 删 staging → 更新 status
- 防部分失败: 任一步失败回滚 status=failed, 不删 staging

## D5: 并发冲突 = DB unique constraint
- tasks 表 UNIQUE(series_id, season_number, episode_number)
- 仅对 active 任务生效 (committed 完成后允许新任务覆盖)
- 失败抛 IntegrityError → HTTP 409

## D6: 容器权限 = UID 1000
- Dockerfile 创建 appuser (UID 1000)
- 与 Emby UID 匹配或共享 group
- chmod 644 移动后的文件

## D7: 后端工具链 = pyproject + ruff.toml + mypy.ini
- `pyproject.toml` 放项目元数据、依赖、pytest、setuptools editable 安装
- `ruff.toml` 放 lint/format 主配置，`[tool.ruff]` 只做入口
- `mypy.ini` 独立，strict + `ignore_missing_imports`
- 原因: 配置分层清楚，后面 T4+ 直接复用

## D8: 前端工具链 = Vite + Vue 3 + Vitest + ESLint + Prettier
- `vite.config.ts` 负责 dev/build/proxy，`vitest.config.ts` 负责 jsdom 测试
- `src/env.d.ts` 统一补 `.vue` 模块声明
- `naive-ui/dist/preset.css` 用 alias 兜底到本地 shim，避免上游包缺文件导致构建炸掉
- 原因: 骨架先跑通，再让后续任务接业务代码

## D9: 异步 SQLAlchemy 2.0 模式
- Base = DeclarativeBase 子类 (mypy strict 友好)
- engine = create_async_engine(settings.database_url), SessionLocal = async_sessionmaker(expire_on_commit=False)
- 建表: `async with eng.begin() as conn: await conn.run_sync(Base.metadata.create_all)`
- init_db(target_engine=None) 默认用模块 engine, 测试注入内存库
- main.py 用 lifespan(asynccontextmanager) 启动调 init_db, 不破坏 /health
- 时间戳走 TimestampMixin (created_at/updated_at, default/onupdate=func.now())

## D10: 路径安全策略 = 单一入口 + allow-list 白名单
- 所有文件系统读写必须经过 `app.utils.path_security.safe_resolve` 校验，禁止业务层直接 `Path.resolve` 后信任。
- `allowed_roots` 在业务侧由配置（`Libraries` 表）动态注入，传给 safe_resolve；空 allow-list 主动报错，避免默认放行。
- symlink 不单独禁用，而是依赖 `resolve(strict=False)` 自动跟随 + allow-list 复核结果。
- 原因: T5 OWASP Path Traversal 防护成本最低、误伤最小，同时为 T6 命名模板、T11 文件移动提供统一前置。

## D11: sanitize 默认占位符 = `Untitled`
- 当输入清洗后为空或仅剩 `_`/空格时，统一回落到 `Untitled`。
- 原因: 避免剧集目录出现 `.`、空名、`___` 等不可点开/无法识别的占位。

## D12: Kodi v12 episode NFO 字段约定
- 根元素固定 `<episodedetails>`，与 Kodi movie `<movie>` 区分；Emby/Jellyfin 扫描器按根元素路由解析器。
- 字段集对齐 Kodi v12 episode schema：`title/season/episode/plot/premiered/year/genre/tag/actor/director/studio/rating`，v1 不扩展。
- 多值字段（`genre`/`tag`/`director`）展开为同名多个子元素（如 `<genre>剧情</genre><genre>科幻</genre>`），不放在容器里。
- `actor` 单独成结构 `<actor><name/><role/></actor>`，role 缺省时不生成 `<role>` 标签。
- XML 声明头：`<?xml version='1.0' encoding='UTF-8' standalone='yes'?>`，固定 standalone='yes' 兼容老 Kodi 解析器。
- 原因: Kodi wiki episode NFO 是事实标准（Emby/Jellyfin 都吃这套），贴齐可避免自定义 schema 兼容性踩坑。
