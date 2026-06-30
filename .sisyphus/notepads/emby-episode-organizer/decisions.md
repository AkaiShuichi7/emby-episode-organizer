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

## D13: 日志轮转策略 = 10MB / 5 份
- 控制台和文件都走同一份 JSON formatter，便于本地调试和后续集中采集。
- 文件用 `RotatingFileHandler(log_dir / "app.log", maxBytes=10*1024*1024, backupCount=5, encoding="utf-8")`。
- 初始化时先清空 root handlers，避免 FastAPI lifespan 重入后重复写日志。
- 原因: stdlib 最小实现，够用先上；后面真要接 ELK 再换采集层，不改业务日志调用点。

## D14: 移动原子性策略 = 全量 tmp 校验后统一 rename
- staging 阶段只复制源视频、写 NFO、可选复制封面，不接 DB/BackgroundTasks，保持核心逻辑可测。
- commit 阶段先检查目标冲突；任一同名目标存在直接抛 `FileConflictError`，不动 staging。
- commit 阶段先复制全部 staging 文件到目标目录同名 `.tmp` 并校验大小，再用 `os.rename` 统一落地，最后删除 staging。
- 失败回滚只清理本次 `.tmp` 和已创建 target，保留 staging；API 层 T18 再负责把 Task 状态置为 `failed`。
- 原因: 比逐文件 copy→rename→删 staging 更安全；后者中途失败会丢 staging，无法重试。

## D14: 设置键命名约定 = `<domain>.<field>`
- 全部走扁平字符串键，按业务域前缀分组：`emby.server_url` / `emby.api_key` / `emby.auto_refresh` / `file.source_mode` / `file.allowed_browse_roots`。
- 默认值集中在 `app.services.settings.DEFAULT_SETTINGS`，key 名即契约，测试用 `assert set(DEFAULT_SETTINGS) == {...}` 锁定，避免误改。
- 原因: 扁平键天然适配 JSON 列 + ORM 通用读写；按域前缀分桶，后续 settings API 路由可按前缀分组展开。

## D15: API Key mask 永远在响应层，不在 DB
- DB 存明文（按 T12 设计），只在 GET 响应序列化前过一道 mask 函数。
- 掩码规则：长度 >= 4 显示 `xxxx****{last4}`，更短整体替换为 `****`，非字符串/空值原样返回。
- 集中维护在 `app/api/v1/settings.py` 的 `_MASKED_FIELDS` 集合，新增敏感字段只追加这一行，端点逻辑零改动。
- 原因：避免散落各端点；mask 函数有单测覆盖（`test_get_settings_masks_api_key`），未来加新敏感 key 不必复制粘贴逻辑。

## D16: API 版本化 = URL 前缀 + 总 router + 子模块自挂载
- 全局 `api_v1_router = APIRouter(prefix="/api/v1")` 集中在 `app/api/v1/__init__.py`。
- 各业务子模块（settings / emby / libraries / series / tasks）在文件底部 `api_v1_router.include_router(router)` 自挂载。
- 触发方式：子模块不放进 `v1/__init__.py`（避免循环 import），由 `app/main.py` 显式 import 触发。
- 原因：循环 import 来自 `v1/__init__.py` 想 import 子模块、而子模块又要 import `api_v1_router` 的死锁。`main.py` 作为顶层组装者最合适做这一步；后续 T15-T18 各自子模块只管 `include_router` 一行，新加 import 即可。

## D17: 库 CRUD 不级联删除
- v1 `DELETE /api/v1/libraries/{id}` 只删 Library 行，不删 / 不改关联 series；删除前不查关联 series 数。
- 原因: 整理任务的 series / task 是独立域，删除 Library 不应该顺手把用户已经维护好的 series 一并清理；后续 T22+ 显式处理"删除库时迁移/隐藏 series"的业务决策。v1 简单优先。

## D18: API 路径校验统一从 settings 读 allowed_browse_roots
- 所有需要校验目录越界的 API 端点（libraries、series、tasks）通过 `Depends(get_settings_service)` 读取 DB 中 `file.allowed_browse_roots`，再调 `safe_resolve`。
- 不再走 `app.config.settings.allowed_browse_roots`（pydantic-settings 启动加载）和 DB 双轨；统一 DB 为唯一可信源，运维改 settings API 立刻生效，无需重启。
- `safe_resolve` 校验失败抛 HTTPException 400，detail 包含字段名（`staging_root` / `target_root`），前端按字段定位。
- 原因: 与 D10 路径安全策略对齐；DB 作为运行时单一配置源，避免"环境变量改了但没重启导致数据库 vs 代码不一致"类问题。
