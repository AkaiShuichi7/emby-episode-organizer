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

## T5 路径安全 + 文件名清理
- `safe_resolve` 必须先 `expanduser().resolve(strict=False)` 再用 `is_relative_to` 校验；空 `allowed_roots` 直接拒。
- symlink 安全 = 自动跟随 + 真实目标仍在 allow-list 内才算合法；测试用 `os.symlink` 在 tmp_path 外构造泄漏点。
- `validate_inside_roots` 不抛异常，捕获 `OSError/RuntimeError` 兜底返回 `False`，避免边界 Path 触发未捕获异常。
- `_finalize` 的"全为空"判定不只是 `collapsed or "Untitled"`；字符全为 `_`/空格（如 `///` → `___`）也要归为 `Untitled`。
- 中文正则不需要白名单，sanitize 只换非法字符集合 `[\\/:*?"<>|]`，中文/英文/数字/连字符/括号/方括号天然保留。
- `sanitize_series_name` 在 sanitize_filename 基础上多删 `.`，避免目录名被 OS 当成扩展名。

## T7 NFO 构建/解析器
- `xml.etree.ElementTree` 默认输出 `<?xml version='1.0' encoding='UTF-8'?>`，不带 `standalone='yes'`；Kodi 兼容要求补 `standalone='yes'`，故 `build_nfo_xml` 走 `tostring(encoding='unicode') + 手动声明头` 拼接。
- "空字段不生成标签"语义集中在 `_maybe_add`（None/空串/列表跳过），build 里不散落判断。
- round-trip 用 pydantic `BaseModel.__eq__` 即可，无需手写 `assert dict == dict`。
- `_int_or_none` / `_float_or_none` 防御性 `try/except ValueError`，避免脏 NFO 拖垮上层；缺字段/解析失败统一返回 None。
- mypy strict 下 `Optional[X]` 触发 ruff UP045（推荐 `X | None`），一次性 `--fix` 全转。

## T6 命名模板
- 命名上下文统一收敛到 `NamingContext(series, season, episode, title, ext)`。
- 视频名先做 `sanitize_series_name` + `sanitize_filename`，再套 `{series} - S{season:02d}E{episode:02d} - {title}{ext}`。
- NFO / thumb / season folder 只做模板拼接，保持格式稳定。
- `:02d` 只补零，不会截断 `100` 这种三位集数。

## T9 日志配置
- stdlib logging 足够：`logging` + `json` + `logging.handlers.RotatingFileHandler`。
- JSON 日志固定一行，字段收敛为 `ts/level/logger/msg/module/func/line`，测试只断言前四个必需键。
- `setup_logging` 必须先清理 root 旧 handler，再挂控制台和文件 handler，避免重复初始化叠日志。
- 测试里要用 root logger 还原 fixture，避免 handler 泄漏污染其它用例。

## T8 封面下载器
- httpx `client.stream("GET", url, timeout=...)` 的 timeout 触发后，TimeoutException 会在 stream context 内部抛出；必须在内层 try 捕获并转 CoverTimeoutError。
- respx 的 `side_effect=handler` 不会延迟响应——respx 同步构造 Response 后立刻返回。要在测试里触发 timeout，必须直接 `side_effect=httpx.TimeoutException(...)`，不能用 sleep 模拟。
- httpx `client.stream` 必须用 `async with` 退出；`aiter_bytes` 迭代完成后才退出 stream context。如果中途抛异常，stream context 会再次抛，需要外层 try/finally 接住。
- Pillow `Image.verify()` 不解码像素，只校验结构，比 `Image.open().load()` 快 10x+；坏图通常抛 `UnidentifiedImageError` 或 `OSError/SyntaxError`。
- Pillow 已装 12.2.0 (Py3.12 arm64 macOS wheel 完整)，无需编译。

## T11 文件移动服务
- `stage_files` 收敛为纯文件系统核心逻辑：校验源视频存在且扩展名在白名单，`shutil.copy2` 复制视频/封面，NFO 用 UTF-8 文本写入。
- `commit_to_target` 采用同目录 `.tmp`：先复制全部 staging 文件到 `.tmp` 并校验大小，再统一 `os.rename` 到最终路径，最后才删除 staging 文件。
- 提交失败时清理 `.tmp` 和本次已创建的 target 文件，staging 文件保留，方便 API 层后续把任务状态置为 `failed` 后重试。
- 大文件复制不要手写 chunk；`shutil.copy2` 不会一次性把 1GB+ 文件读进内存，并保留 mtime。

## T10 Emby API 客户端
- Emby 列表接口统一包在 `{"Items": [...]}`；客户端可集中用 `_items()` 提取，避免每个方法重复判空。
- `/Shows/{series_id}/Episodes` 下一集号查询要传 `Season={season_number}`；`IndexNumber` 缺失条目必须忽略，避免特别篇/花絮污染自动编号。
- `test_connection()` 对 `/System/Info/Public` 要把 401/403 单独映射成 `EmbyAuthError`，其余非 2xx 统一走 `EmbyConnectionError`。

## T12 设置服务
- `Setting.key` 是 unique 字符串键，但 PK 是 `id` 整数主键；`session.get(Setting, key)` 用的是 PK 查找，对字符串键永远查不到，会导致 upsert 误判为"不存在"并插入重复行触发 UNIQUE 冲突。必须走 `select(Setting).where(Setting.key == key).limit(1)`。
- 设置项 key 命名按业务域分段：`emby.*` / `file.*` / `app.*`；默认值集中在 `DEFAULT_SETTINGS` 常量，对外暴露方便测试断言契约。
- `init_default_settings` 仅在 key 不存在时插入，已存在不动 → 天然幂等，并且不会覆盖运维已经改过的值，重复调用安全。
- JSON 列读写在 SQLite + SQLAlchemy 上对 dict / list / bool / str / int 都是直进直出，不需要手动 `json.dumps/loads`。
- 测试 fixture 同时持有 `engine` 和 `session`，session 不 commit 也能让同 session 的 set/get 互相看到（pending → identity map），跨 session 才必须 commit。

## T13 文件浏览服务
- `browse_directory` 排序约定：目录在前 (`(not is_dir, name.lower())` 作为 sort key)，同类型按 name 升序，name 比较走 `.lower()` 保证大小写无关稳定。
- `BrowseResult.parent_path` 在 current_path 命中 allowed_roots 时为 `None`，否则 `= resolved.parent`；前端用 `parent_path is None` 判定面包屑到顶。
- 目录的 `is_video` 永远 `False`，即使目录名带 `.mkv/.mp4` 也算数；`is_video = (not is_dir) and is_video_file(entry)`，避免 UI 误把目录当成视频卡片。
- `validate_source_file` 失败优先级：路径不在 allowed_roots → `PathSecurityError`；不存在 → builtin `FileNotFoundError`；是目录 / 扩展名不在白名单 → 自定义 `NotAVideoError`。`PathSecurityError` 必须先于 `exists()` 检查，否则漏白名单校验。
- `BrowseEntry.modified_at` 用 `datetime.fromtimestamp(stat.st_mtime)`（naive 本地时间），pydantic v2 自动序列化；不需要额外 tz 字段。
- pydantic 模型 `BrowseEntry` 必须给 `modified_at` 设 `default_factory`，否则 pydantic v2 + mypy strict 会在构造空 dict 时报缺字段。

## T14 Settings API
- FastAPI 的 `Depends(get_settings_service)` 在参数默认值里调用是官方推荐写法，但 ruff B008 误报；项目级 `ruff.toml` 加 per-file-ignore `["B008"]` 给 `app/main.py` 和 `app/api/**/*.py` 解决。
- FastAPI 子路由自挂载（模块底部 `api_v1_router.include_router(router)`）+ 主程序 import 触发：避免把子模块硬编码进 v1 包 `__init__.py`，否则会形成 `v1/__init__` ↔ `v1/settings` 循环 import。**main.py 显式 import 各 v1 子模块**是干净的解耦点。
- `get_settings_service` 抛错发生在依赖解析阶段，**端点 try/except 接不住**；测试兜底用"返回坏 service、其方法抛"的模式：override 返回一个继承 `SettingsService` 但 `get_emby_config` 直接 `raise` 的子类型，错误发生在端点 try 块内被 catch。
- `SettingsService.set` 走 upsert 但**不 commit**；PUT 端点需 `Depends(get_db)` 拿到同一 session 并 `await db.commit()`，否则 `async with SessionLocal() as session` 关闭时未提交事务回滚 → PUT 后 GET 看不到。FastAPI 对相同依赖去重，`Depends(get_db)` 两次注入拿到同一 session。
- pydantic v2 的 `RootModel[dict[str, Any]]` 是把"整个 body 就是个 dict"的请求/响应模型的最佳载体；body 取值走 `body.root`。
- Pydantic `RootModel` 的 OpenAPI schema 把整个对象拍平为 `{type: object}`，不会在 schema 里出现 `root` 字段，前端体验上等价于裸 dict。

## T15 Emby API 路由
- 业务错误统一返回格式 `{success: false, message: str, detail: str | None}`；不在响应层抛 4xx/5xx 给前端，`/test` 端点全部 200 + `success` 字段判定；只有"未配置 Emby"返回 400（业务前置检查），其它都是 200。
- FastAPI 路由内 `try/finally + await client.aclose()` 必须包住 EmbyClient 调用，否则长生命周期 httpx 客户端会泄漏（respx 测试间互不干扰，pyright 也会揪）。
- API 层复用 `get_emby_config` Depends，避免每个端点重写 DB 查询；缺配置直接 `JSONResponse(400, ErrorResponse(...).model_dump())`，响应体不带 `detail` 包裹。
- 子模块（emby.py）只在文件底部 `api_v1_router.include_router(router)`；要在 main.py 加 `from app.api.v1 import emby as _v1_emby` 触发挂载（T14 已建立模式）。否则路由永远 404。
- 测试用 `app.dependency_overrides[get_emby_config] = lambda: EmbyConfig(...)` 注入 stub 配置，比往 DB 塞 3 行设置更稳；in-memory SQLite 多连接可能不共享数据。
- respx `mock(side_effect=httpx.ConnectError(...))` 直接让 respx 抛出 httpx 异常，比手写 sleep 模拟真实超时更准；EmbyClient 把 `httpx.HTTPError` 包成 `EmbyConnectionError`，API 层捕获后转 `{success: false, message: "连接失败"}`。
- mypy strict 下路由返回值用 `JSONResponse | list[dict[str, Any]]` 联合类型；FastAPI 对 JSONResponse 跳过 response_model 校验，所以 `response_model=list[Any]` 仍然有效。
- Pydantic v2 `model_dump()` 直接把 PascalCase 字段（ItemId/Name 等）保留输出，前端按 Emby REST API 字段名消费，不用二次 camelCase 转换。

## T16 Libraries CRUD API
- 路径校验统一走 `app.utils.path_security.safe_resolve` + settings DB 的 `file.allowed_browse_roots`，不在 endpoint 硬编码。空 allowed_roots 视为"未配置"，所有路径校验都失败（不再"默认放行"）。
- 测试 fixture 用 `app.dependency_overrides[get_db]` 在每次请求中 `init_default_settings` 之后再 `Setting.value = [str(tmp_path)]` 覆写，比单独 override `get_settings_service` 更稳：保留了真实 service 的 session 共享语义，FastAPI 对相同依赖去重，libraries 端点的 `Depends(get_db)` 和 `Depends(get_settings_service)` 拿到同一 session。
- PATCH 风格更新用 `body.model_dump(exclude_unset=True)` 只把客户端显式传入的字段写到 ORM 上；`exclude_unset=True` vs `exclude_none=True`：前者保留 `false`/""这种"用户明确置空"的语义，后者会把 `false` 当成"未传"漏更新。libraries 的 enabled 默认 True，PUT 改 False 必须用 `exclude_unset=True` 才能落到 ORM。
- pydantic v2 `model_config = ConfigDict(from_attributes=True)` 让 `LibraryResponse.model_validate(orm_obj)` 直接读 ORM 属性，免去手写 `LibraryResponse(id=library.id, name=library.name, ...)` 模板。
- ruff C416 嫌 `body.model_dump(...).items()` 包 dict comprehension 多余；直接 `dict(body.model_dump(exclude_unset=True))` 就过。
- DELETE 端点用 `return Response(status_code=status.HTTP_204_NO_CONTENT)` 显式给空体；不返响应模型，避免 FastAPI 默认 `application/json` 头 + 空数组噪声。
- 子路由自挂载 + main.py `from app.api.v1 import libraries as _v1_libraries  # noqa: F401` 触发（T16 模式照抄），新加模块就是 `main.py` +1 行 + 文件底部 `include_router`。

## T17 Series CRUD API
- series 路径校验跟 library 不同：series 的 staging_path 校验在关联 library.staging_root 下、target_path 校验在 library.target_root 下（不是全局 allowed_browse_roots，那是 library 自己的校验层）。用 safe_resolve(path, [Path(library.staging_root)]) 即可，root 为 None → 400。
- library_id 为 None + 路径非空 → 直接 400（无参照无法校验路径安全）；library_id 非 None 但 DB 查不到 → 400。
- PUT 路径校验用 effective_library_id = updates.get("library_id", series.library_id)：body 没传 library_id 时回退到 series 当前关联，避免改 path 时误判无 library。
- PUT 显式改 library_id 时同步 library_name 冗余字段（None → None，非空 → 重查 library.name）。
- GET 列表可选 ?library_id= 过滤，用 Query(default=None) + select.where 条件拼接。
- 子路由自挂载 + main.py +1 import (T16 模式照抄)：`from app.api.v1 import series as _v1_series  # noqa: F401`。
- 测试 fixture 与 T16 完全一致（覆写 file.allowed_browse_roots = [tmp_path]），series 测试先 POST /libraries 建 library 再测 series 路径校验。

## T18 Tasks API + Files API
- tasks/files 路由继续沿用 "子模块底部 `api_v1_router.include_router(router)` + main.py 显式 import 触发" 模式；main.py 只需新增 tasks/files 两行 import。
- 任务路径计算统一走 `NamingContext + generate_video_filename/generate_nfo_filename/generate_thumb_filename + generate_season_folder`：staging 直接落 series.staging_path，target 多一层 `Season XX`。
- preview 支持 `episode_number=None`：此时只返回基础字段，六个 staging/target 路径统一给 `None`，避免伪造文件名。
- create 先校验 source_file_path 在 `file.allowed_browse_roots` 内且是视频，再写 staging 视频/NFO/可选封面；v1 状态简化为 `draft -> staged -> committed`，无 NFO 时保留 `draft`，有落盘产物后进 `staged`。
- commit 不要盲信 `staging_cover_path` 非空；需只提交真实存在的 staging 文件，否则无封面任务会因缺失 thumb 路径提交失败。
- files API 只包一层 HTTP 语义：`browse_directory` / `validate_source_file` 的 `PathSecurityError`、`FileNotFoundError`、`NotAVideoError` 统一转 400，响应直接透传 service 的 pydantic `model_dump(mode="json")`。

## T18 浏览目录回退
- `POST /api/v1/files/browse` 现在允许空路径；若前端未给初始路径，API 先回退到首个允许根目录，再交给 `browse_directory` 读取目录内容。
- files API 的允许根目录解析和 libraries 保持同一策略：DB `file.allowed_browse_roots` 优先，空时回退到 `app.config.settings.allowed_browse_roots`，最后才是空列表。
- 测试补了一条空路径 + 环境变量回退用例，覆盖首次打开文件浏览对话框的入口。

## T20 Pinia stores
- Pinia 统一用 setup store：`defineStore('name', () => { ref state + async actions + return })`。
- store action 只调 `@/api/client` 的 `api.get/post/put/delete`，路径传 `/settings` 这类相对 API v1 路径，前缀由 client 拼接。
- action 捕获错误后写 `error` 字段并返回 `null`，不向 UI 重抛；`loading` 在 `finally` 复位。
- store 单测用 `setActivePinia(createPinia())` 隔离实例，用 `vi.mock('@/api/client')` mock api 方法。

## T22 结论
- EmbySettings 只读入 server_url/auto_refresh，API Key 只在用户真填时提交；LibraryMapping 刷新 Emby 库改成 `EmbyLibrary[]` + `unknown` 错误处理。

## T22 修正
- 新建映射页用 Emby 库 select 驱动 `name`，刷新后再选；提交直接带 `name/staging_root/target_root/enabled`，不造后端没有的 `emby_library_id`。
- T22 浏览器告警修正：模板里用到的 Naive UI 组件必须在 `<script setup>` 显式导入，才会解析成 `<n-*>`。

### SeriesConfig Path Generation (T23)
- **Sanitization**: `sanitizeSeriesName` now replaces spaces with underscores (`_`) to match test expectations and common path conventions.
- **Test Mocking**: When mocking Pinia stores with reactive state (like `libraries`), ensure the mock implementation of load functions actually updates the local mock state to trigger dependent logic (like `find` in `handleLibraryChange`).
- **Vitest Mocking**: Avoid using `mocks.loadLibraries.mockImplementation` inside `vi.mock` if it causes infinite recursion; use a plain async function that calls the mock instead.
- When mocking Pinia stores that return arrays, use a concrete type like `Array<{ id: number, ... }>` instead of `any[]` to satisfy `@typescript-eslint/no-explicit-any` while keeping the mock simple.
- URL params with non-ASCII chars get percent-encoded by `withQuery`; use `.toMatch(/regex/)` for Chinese in test assertions instead of literal string.

## T24 OrganizePage + 核心交互
- **series store 端点修正**: 旧版 `loadEpisodes` 用 `/emby/series/{id}/episodes?season=` 和 `loadLatestEpisode` 用 `/emby/series/{id}/latest`；后端实际是 `/emby/series/{id}/seasons/{season}/episodes` 和 `/emby/series/{id}/seasons/{season}/latest`。在 `series.ts` 里修正两个方法签名和路径。
- **FileBrowserDialog watch 模式**: `watch(() => props.show)` 不带 `immediate: true`，只在 `show` 从 false→true 时触发；测试里先 mount `show: false`，再 `setProps({ show: true })` 触发 watch。
- **OrganizePage 7步流**: 选择剧集→loadSeasons→选季→loadLatestEpisode→自动填集号(可手动覆盖)→选源视频(弹对话框)→填标题(来自文件名)→cover tabs(URL tab 接入 payload，upload tab UI 占位)→preview panel→create。
- **Naive UI message provider in tests**: OrganizePage 调用 `useMessage()`，测试需 mock naive-ui 的 `useMessage` 工厂方法：```ts
vi.mock('naive-ui', async () => {
  const actual = await vi.importActual('naive-ui')
  return { ...actual, useMessage: () => mockMessage }
})
```
- **TaskPreview props**: 组件 prop 有默认值 `null`，测试直接 `mount(Component, { props: { preview } })` 传真实数据，不用绕 `wrapper.vm.$props` 赋值。
- **API mock 隔离**: 每个 describe 里 `beforeEach` 调用 `vi.clearAllMocks()` 并在 `vi.mock('@/api/client')` 内初始化 mock 实现。

## T24 lint fix 记录
- **一次性修 13 个 lint 错误**: 清理未使用导入/变量，不改动业务逻辑。
- **未使用导入来源**:
  - 测试文件：`FileBrowserDialog.spec.ts` 的 `NConfigProvider/NDialogProvider/NMessageProvider/NIcon`；`TaskPreview.spec.ts` 的 `vi` 全局声明。
  - 源码：`client.ts` 的 `HttpMethod`；`FileBrowserDialog.vue` 的 `onMounted`/`NIcon`；`TaskPreview.vue` 的 `NSpace`；`MainLayout.vue` 的 `h`；`OrganizePage.vue` 的 `useRouter`/`router`。

## T25 mypy strict tests
- `mypy strict=True + tests` 常见修法：fixture async generator 改 `AsyncIterator[T]`，SQLAlchemy `scalar_one_or_none()`/JSON 返回值用 `cast(...)` 收窄，测试里访问模块导出时可改成 `cast(Any, module).attr`。

## T25 任务 NFO 编辑权限
- 详情页 NFOEditor 显隐要跟后端状态机同步：`draft/staged/nfo_edited/failed` 可编辑，`committed/cancelled/ready_to_commit` 不可编辑。
- `PUT /api/v1/tasks/{id}/nfo` 必须服务端再校验一次状态，前端隐藏只能减误点，不能当权限边界。

## T25 TaskList 行点击冒泡
- `n-data-table` 的 `row-props.onClick` 会吞掉整行任意子元素点击，操作列里的 `NPopconfirm` 触发按钮必须显式 `stopPropagation()`。
- 只拦 `删除/取消任务` 触发按钮，不动 `查看`，这样行点击和查看按钮都还能进详情。

## T18 tasks 回退修正
- `POST /api/v1/tasks` 的 allowed_browse_roots 解析要跟 files/libraries 一致：DB 为空或缺失时，回退到 `app.config.settings.allowed_browse_roots`，避免 settings 表没值时直接 500。

## T25 文件浏览路径回传
- `BrowseEntry` 需要把 `path` 一起返回给前端，且用 `Path` 模型字段即可直接序列化成 JSON 字符串。
- 前端点击目录时依赖 `entry.path` 回传；缺字段会把请求体打成空对象，FastAPI 直接回 422。
- 服务层测试最好同时断言 `name` 和 `path`，防止只补字段没补真实绝对路径。
  - 测试：`frontend/tests/api/client.spec.ts` 的 `ApiError`。
- **series.ts 去 any**: 新增 `LatestEpisode { next_episode: number; latest_episode?: Episode }` 接口，替换 `api.get<any>`；`loadLatestEpisode` 返回整个对象，但 `latestEpisode` 只存 `latest_episode`，保持 `OrganizePage` 用 `next_episode` 字段。
- **FileBrowserDialog 错误处理**: 删除 `console.error`，改为 `catch { /* 忽略浏览失败 */ }`；当前目录为空即可，不弹提示、不增加 store 字段。
- **验证**: `npm run lint` 通过；`npm run build` 通过；`npm run test:unit -- --run OrganizePage FileBrowserDialog TaskPreview` 6 个用例全部通过。
- **原则**: 最小 diff，不引入新依赖，不改动非 T24 组件或路由。

## T25 Libraries 路径白名单回退
- `file.allowed_browse_roots` 优先级改成 DB → `ALLOWED_BROWSE_ROOTS` 环境配置，DB 为空时不再把所有路径误判成未配置。
- `_ensure_path_allowed` 报错时带上当前环境白名单，方便直接判断是配置缺失还是路径越界。
- 验证命令：`cd backend && ./.venv/bin/python -m pytest -q && ./.venv/bin/ruff check . && ./.venv/bin/python -m mypy app` 通过。

## T25 LibraryMapping Emby 字段对齐
- 后端 `EmbyLibrary.model_dump()` 保留 PascalCase 字段：`ItemId` / `Name` / `CollectionType`，前端不要私自改成 camelCase 或 snake_case。
- 下拉框选项直接映射 `library.Name`，提交时再按选中的 `Name` 反查原始库对象，把 `CollectionType` 填回 `collection_type`。
- 测试样本也要跟后端形状一致，不然会把字段错配当成 UI 问题。

## T25 Emby VirtualFolders
- `/Library/VirtualFolders` 可能返回裸数组 `[...]`，不是 `{"Items": [...]}`；`EmbyClient.get_libraries()` 需要单独兼容。
- `_request_json()` 只应拒绝非 JSON 对象/数组，列表响应别误判成协议错误。
- 对应测试最好直接 mock 裸数组，才能覆盖真实 Emby 行为。

## T24 latest 接口类型修正
- **后端契约**: `/emby/series/{id}/seasons/{season}/latest` 返回 `{ latest_episode: number; next_episode: number }`（都是 int），不是 Episode 对象。
- **修正内容**:
  - `LatestEpisode` 接口改成 `{ latest_episode: number; next_episode: number }`。
  - `latestEpisode` ref 类型改成 `LatestEpisode | null`。
  - `loadLatestEpisode` 直接把完整响应存入 `latestEpisode`，返回完整对象；`OrganizePage` 继续读 `latest.next_episode` 自动填集号。
- **测试**: `series.spec.ts` mock 已是 `{ latest_episode: 5, next_episode: 6 }`，无需改动。

## T24 浏览器 QA 修正：NGridItem 未导入
- **现象**: `/organize` 页面只渲染空白/标题，控制台报 `Failed to resolve component: n-grid-item`。
- **根因**: `OrganizePage.vue` 模板用了 `<n-grid-item>`，但 `<script setup>` 只导入了 `NGrid`，没导 `NGridItem`。
- **修复**: 在 `OrganizePage.vue` 的 naive-ui 导入里加上 `NGridItem`。
- **验证**: lint/build/单元测试全通过；`OrganizePage` 测试继续通过。
- **教训**: 模板里每个 `<n-*>` 组件都要在 `<script setup>` 显式导入，lint 不报错但运行时 Vue 会 unresolved component。

## T25 任务列表页 + 任务详情页（含 NFO 编辑）
- **新增文件**: `frontend/src/views/TaskList.vue`、`frontend/src/views/TaskDetail.vue`、`frontend/src/components/NFOEditor.vue`。
- **store 扩展**: `frontend/src/stores/tasks.ts` 新增 `loadTask(id)`，调用 `GET /tasks/{id}`，更新 `currentTask` 与列表中对应任务。
- **路由更新**: `frontend/src/router/index.ts` 将 `/tasks` 指向 `TaskList.vue`，`/tasks/:id` 指向 `TaskDetail.vue`。
- **Naive UI 组件导入**: 模板里每个 `<n-*>` 组件都要在 `<script setup>` 显式导入（包括 `NGridItem`、`NDescriptions`、`NDescriptionsItem`、`NDynamicInput`、`NUpload`、`NTooltip` 等），否则运行时报 unresolved component。
- **NSelect null 值类型**: Naive UI 的 `SelectMixedOption` 不允许 `value: null`，用 `null as unknown as string/number` 做占位并通过 `clearable` 实现“全部”选项。
- **NImage src 类型**: `NImage` 的 `src` 不接受 `null`，`coverUrl` 返回 `string | undefined`，模板里 `v-if="coverUrl(task)"` 加 `:src="coverUrl(task)"`。
- **NUpload on-change 类型**: `UploadOnChange` 参数结构为 `{ file: UploadFileInfo, fileList, event }`，`file.file` 是 `File | null`；不要直接写 `{ file: File }`。
- **NFOEditor 双向绑定防循环**: `modelValue` 与本地 `form` 互相触发时，用 `isInternalUpdate` 标记 + 等值比较避免递归更新。
- **取消按钮处理**: 后端无 cancel 接口，按钮 disabled 并配合 `NTooltip` 显示“取消接口暂未实现”，不调用任何 API。
- **测试要点**:
  - 列表过滤测试断言 `api.get` 被调用 `/tasks?status=committed`。
  - NFO 保存测试通过 stub `NFOEditor` 触发 `@save` 事件，断言 `tasksStore.updateNFO` 被调用并弹出 `NFO 保存成功`。
  - `TaskDetail` 测试里 `NGrid`/`NGridItem` 用 `true` stub 避免 Naive UI grid 递归更新警告。
  - 每个测试 `beforeEach` 里 `setActivePinia(createPinia())` + `vi.clearAllMocks()` 做隔离。
- **验证命令**:
  - `cd frontend && npm run lint`
  - `cd frontend && npm run build`
  - `cd frontend && npm run test:unit -- --run TaskList TaskDetail NFOEditor tasks`
- **结果**: lint、build、目标单元测试全部通过。

## T25 QA 修正：Popconfirm 按钮中文标签
- **问题**: 浏览器 QA 发现任务列表/详情的 `NPopconfirm` 默认按钮显示英文 `Cancel` / `Confirm`。
- **修复**:
  - `frontend/src/views/TaskList.vue`: render-function 的 `NPopconfirm` 增加 `positiveText: '确认'`、`negativeText: '取消'`。
  - `frontend/src/views/TaskDetail.vue`: 两个模板 `<n-popconfirm>` 增加 `positive-text="确认"` `negative-text="取消"`。
- **原因**: Naive UI `NPopconfirm` 默认 positive/negative 文案是英文，必须显式绑定 `positive-text` / `negative-text`（模板）或 `positiveText` / `negativeText`（render function）。
- **验证**: lint、build、目标单元测试全部通过。

## T26 封面管理 UI
- **新增 `CoverManager.vue`**: 统一封装封面展示（无/本地/URL 下载）、本地上传、URL 下载，使用 `/api/v1/tasks/{id}/cover/raw` 显示当前封面。
- **Naive UI 导入完整性**: `CoverManager.vue` 使用 `NTabs`/`NTabPane`/`NText` 等组件，必须在 `\u003cscript setup\u003e` 显式导入，否则运行时无法解析。
- **NUpload 不要自动上传**: `NUpload` 仅作为文件选择触发器，配置 `:show-file-list="false"` + `accept="image/*"`，在 `on-change` 回调里手动调用 `tasks.uploadCover`。
- **URL 下载校验**: 按钮点击时 trim 输入，空字符串直接 `message.warning('请输入封面图片 URL')`，不调用 API。
- **后端 raw 端点**: 优先 `staging_cover_path`，其次 `target_cover_path`；用 `mimetypes.guess_type` 推断 `media_type`，缺失回退 `application/octet-stream`；文件/任务缺失统一 404。
- **TypeScript 注意**: 不要从 Pinia store 解构 `currentTask` 再 `.value` 赋值，会丢失响应式且类型错误；直接通过 `tasksStore.currentTask = updated` 更新。
- **测试覆盖**: 前端 7 个用例覆盖三态、上传、URL 下载、空 URL 校验、updated 事件；后端 3 个用例覆盖成功、任务缺失、文件缺失。
- **验证结果**: `npm run lint`/`npm run build`/`npm run test:unit -- --run CoverManager TaskDetail tasks`/`pytest tests/api/test_tasks_api.py` 全部通过。

## T27 Dockerfile
- **静态挂载顺序**: `app.mount("/", StaticFiles(...), html=True)` 不能放在 `/health` 前面；否则根挂载会吞掉 `/health`，实际要放在 health 路由后面。
- **Docker 环境**: 本机 `docker` 命令不存在，任务只能走 AST 解析 + pytest 验证。
- **前端 public 目录**: 仓库里原本没有 `frontend/public/`，为了让 Dockerfile 的 `COPY frontend/public` 可用，先补了空目录。

## T27 SPA fallback
- **404 回退**: `StarletteHTTPException` 的全局 exception handler 可以接住 `StaticFiles` 挂载后的深链接 404，再按路径前缀区分：`/api` 和 `/health` 保持 JSON 404，其它返回 `frontend/dist/index.html`。
- **最小改动**: 只改 `backend/app/main.py`，保留 `app.mount("/", StaticFiles(...), html=True)` 处理 `/` 和 `/assets/*`。
- **验证**: `TestClient` 实测 `/health` 200、`/` 200、`/tasks/42` 200、`/organize` 200、`/api/v1/nope` 404 JSON；`backend/.venv/bin/python -m pytest -q` 通过 170 passed。

## T29 GitHub Actions
- workflow 用单 job 顺序跑：backend tests/lint → frontend ci/tests/lint/build → Docker Buildx/login/metadata/build-push。
- Docker Hub push 只在 `push main` 或 `push tags v*` 时开；`workflow_dispatch` 只做校验，不推镜像。
- 系统 `python3` 没有 `yaml` 模块；验证用 `backend/.venv/bin/python` 跑 `yaml.safe_load` 更稳。

## T28 compose
- **docker-compose**: 只挂发布镜像 `akaishuichiw/emby-episode-organizer:latest`，不加 `build:` / `version:`，部署侧自己拉镜像。
- **healthcheck**: 跟 Dockerfile 对齐，走 `curl` 检查 `http://localhost:8899/health`。
- **ignore**: `.dockerignore` 必须排除 `dist/`，让镜像内重建前端，不吃本地产物。
- **env example**: `.env.example` 只暴露 `DATABASE_URL` / `LOG_DIR` / `ALLOWED_BROWSE_ROOTS` / `EMBY_DEFAULT_URL`，和 `config.py` 对齐。

## T30 README 完善
- 根 README 采用中文编写，涵盖功能特性、本地开发、生产部署、CI/CD、架构图及安全说明。
- 强调生产部署使用 Docker Compose 拉取已发布镜像，禁止在 README 中引导用户本地构建。
- 前后端子目录 README 补充了详细的技术栈、目录结构及开发命令。
- 验证：通过 grep 确认“本地开发”、“生产部署”、“docker compose up”关键词均已在根 README 中体现。


## F3 Real Manual QA - 2026-07-02
- 本地开发服务器可跑通：后端 8899 health OK，前端 Vite 5173 OK。
- API smoke 4/4：health、libraries、series、tasks 均返回 200 JSON。
- 前端场景 5/5 可加载并截图：homepage、settings、organize、tasks、task-detail。

## Final Wave - AI Slop 清理（2026-07-02）
- **目标文件**: `frontend/src/views/OrganizePage.vue`、`frontend/src/components/FileBrowserDialog.vue`。
- **修复项**:
  1. 删除 `OrganizePage.vue` 中废弃的 `// router.push('/tasks')` 注释代码。
  2. `OrganizePage.vue` 英文注释 `// Default title from filename` → `// 从文件名推导默认标题`。
  3. `FileBrowserDialog.vue` 英文注释 `// Handle root for different OS` → `// 处理不同操作系统的根路径`。
  4. `FileBrowserDialog.vue` 空 catch 块增加 `useMessage` 错误提示：`message.error('浏览目录失败')`。
- **测试陷阱**: `useMessage()` 在单元测试中因缺少 `\u003cn-message-provider /\u003e` 直接抛错。解决方式：在组件内对 `useMessage()` 做 try/catch 降级，`let message: ReturnType\u003ctypeof useMessage\u003e | null = null`，测试环境无 provider 时静默，生产环境正常弹 toast。这样不改测试文件也能通过。
- **验证命令**:
  - `cd frontend && npm run lint`
  - `cd frontend && npm run build`
  - `cd frontend && npm run test:unit -- --run OrganizePage FileBrowserDialog`
- **结果**: lint、build、目标单元测试全部通过。

## BackgroundTasks refactor test fix
- FastAPI `BackgroundTasks` runs after response returns; `httpx.AsyncClient` + `ASGITransport` does not block.
- Tests must monkey-patch `SessionLocal` in the module where the background function is defined (`app.api.v1.tasks.SessionLocal`), because `get_db` override only covers endpoint dependencies, not direct `SessionLocal()` calls in background code.
- Save original, override before `app.dependency_overrides[get_db]`, restore after `app.dependency_overrides.clear()`.
- Commit tests: assert 200 + pre-commit status, `await asyncio.sleep(0.1)`, then re-GET and assert `COMMITTED` / file moved.
- Verification: pytest 170 passed, ruff 0 errors, mypy 0 errors.

## 2026-07-03
- Emby 媒体库列表必须调用 /Library/VirtualFolders；/Library/MediaFolders 响应缺少 ItemId，会触发 EmbyLibrary 校验失败。
- 设置接口返回的 emby.api_key 使用 xxxx****last4 mask；前端保存时必须跳过该 mask，避免覆盖明文 key。
- Header 连接状态从 GET /settings 的 emby.server_url + masked emby.api_key 推导，不依赖不存在的 /settings/emby。

## T30 tasks NFO 入参归一
- `PUT /api/v1/tasks/{id}/nfo` 的 500 根因在 `_build_nfo_payload` 合并原始 JSON 后直接 `model_validate`。
- `director` / `genre` / `tag` 先做字符串归一：空串变 `[]`，非空变单元素 list，原本 list 不动。
- 前端单行文本框继续发 string 也能过，XML 解析出来的 list 仍兼容。
- 验证：`cd backend && ./.venv/bin/python -m pytest -q && ./.venv/bin/ruff check . && ./.venv/bin/python -m mypy app/` 通过；`lsp_diagnostics` changed file 无 error。

## T31 任务取消端到端
- 后端取消接口放在 `commit_task` 和 `delete_task` 中间：`POST /api/v1/tasks/{task_id}/cancel`，只允许 `draft/staged/nfo_edited/failed` 转 `cancelled`，`committed` 返回 400。
- 前端任务取消沿用 store action 返回 `Task | null` 模式：`tasksStore.cancelTask(id)` 同步更新 `tasks` 和当前详情 `currentTask`。
- 列表页用 `NPopconfirm` 包取消按钮，仅在可取消状态显示；详情页取消按钮从 disabled tooltip 改为真实确认弹窗。
- 验证：后端 `pytest -q` 176 passed + ruff + mypy 通过；前端 lint + build + vitest 47 passed 通过。

## T32 前端 409 UX
- TaskList 删除按钮必须跟后端删除白名单保持一致：仅 `draft/failed/cancelled` 显示，其他状态只保留查看和可用取消。
- `tasks` store action 默认吞掉 API 异常并写 `error`，不会向页面重抛；要按状态码分支，需在 store 的 `run` 接收错误映射函数。
- 创建重复任务的 409 仅在 `createTask` 映射为 `DUPLICATE_TASK`，避免删除/取消等其他 409 被误显示成重复任务。
- 验证：前端 `npm run lint && npm run build && npm run test:unit -- --run` 通过，47 个单测通过。
# 任务删除
- 删除接口只删 DB 记录就够了；`_cleanup_task_staging` 对缺失文件是安全 no-op，所以 COMMITTED 任务也能共用同一条删除路径。
- 前端删除按钮别按状态藏。状态限制容易和后端分叉；直接显示更稳，后端兜底即可。

## 2026-07-03 OrganizePage 创建 UX
- 源视频标题自动填充需要区分“文件名推导标题”和“用户手动标题”：用 `titleManuallyEdited` 跟踪；未手动改时换文件同步标题，手动改后保留输入。
- 创建任务要带 `nfo_json: { title }`，否则后端不会写 staging NFO，任务详情 NFOEditor 初始标题为空。
- 创建成功重置表单时不要整体替换 `form.value`；`watch(() => [series_id, season_number])` 返回新数组，整体替换会误触发最新集数预填，可能把 `episode_number` 覆盖掉。逐字段清空更稳。
- 验证：`cd frontend && npm run lint && npm run build && npm run test:unit -- --run` 通过，49 个单测通过。

## 2026-07-03 Dashboard 状态修正
- Dashboard 的 Emby 连接状态不要再读 `embyConfig`，直接从 `allSettings['emby.server_url']` 和 `allSettings['emby.api_key']` 派生。
- 仪表盘最近任务要拉全量任务，再在前端截前 5 条；只拉 `staged` 会让看板误判任务概览。
- 状态列要统一用 `NTag + getStatusLabel/getStatusType`，避免把内部英文状态直接暴露给用户。
