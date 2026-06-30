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
