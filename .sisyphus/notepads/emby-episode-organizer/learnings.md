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
- PATCH 风格更新用 `body.model_dump(exclude_unset=True)` 只把客户端显式传入的字段写到 ORM 上；`exclude_unset=True` vs `exclude_none=True`：前者保留 `false`/`""` 这种"用户明确置空"的语义，后者会把 `false` 当成"未传"漏更新。libraries 的 enabled 默认 True，PUT 改 False 必须用 `exclude_unset=True` 才能落到 ORM。
- pydantic v2 `model_config = ConfigDict(from_attributes=True)` 让 `LibraryResponse.model_validate(orm_obj)` 直接读 ORM 属性，免去手写 `LibraryResponse(id=library.id, name=library.name, ...)` 模板。
- ruff C416 嫌 `body.model_dump(...).items()` 包 dict comprehension 多余；直接 `dict(body.model_dump(exclude_unset=True))` 就过。
- DELETE 端点用 `return Response(status_code=status.HTTP_204_NO_CONTENT)` 显式给空体；不返响应模型，避免 FastAPI 默认 `application/json` 头 + 空数组噪声。
- 子路由自挂载 + main.py `from app.api.v1 import libraries as _v1_libraries  # noqa: F401` 触发（T15 已建立），新加模块就是 `main.py` +1 行 + 文件底部 `include_router`。
