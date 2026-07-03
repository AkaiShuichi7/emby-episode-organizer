# Emby Episode Organizer

局域网 Web 工具，半自动整理 Emby 无法自动刮削的自定义剧集资源（中文命名剧集/动漫等）。

## 功能特性

- Emby 连接测试：验证服务器地址与 API Key 有效性。
- 媒体库映射：配置 Emby 库与宿主机下载/整理/媒体目录的对应关系。
- 剧集路径配置：为不同剧集指定独立的整理缓存与目标路径。
- 单集整理向导：7 步流式操作，涵盖选集、选源、填标题、封面管理。
- NFO 元数据编辑：可视化编辑剧集元数据，支持自定义标签。
- 封面管理：支持本地上传、URL 下载、实时预览。
- 任务列表与详情：追踪整理进度，支持失败重试。
- 安全入库：采用 staging → target 分离模式，提交前不触碰媒体库，支持原子化移动。
- Docker 一键部署：预构建镜像，开箱即用。

<!-- 截图占位：开发完成后补充 -->

## 本地开发

```bash
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8899

# Frontend（另一终端）
cd frontend
npm install
npm run dev
```

前端开发服务器默认 5173，`/api` 自动代理到 `http://localhost:8899`。

## 运行测试

```bash
cd backend && pytest -v
cd frontend && npm run test:unit -- --run
```

## 生产部署

使用 Docker Compose 拉取已发布镜像（CI 自动构建，无需本地 build）。

1. 复制 `.env.example` 为 `.env` 并按需修改配置。
2. 编辑 `docker-compose.yml`：确认挂载路径（downloads/staging/media 的宿主机目录）、config 与 logs 卷。
3. 执行部署：
   ```bash
   docker compose up -d
   ```
4. 访问 `http://服务器IP:8899`。
5. 健康检查：`curl http://localhost:8899/health` 返回 `{"status":"ok"}`。

## CI/CD

仓库 `.github/workflows/docker-build.yml` 在 push 到 `main` 或打 `v*` tag 时自动执行：
- 后端测试：ruff + mypy + pytest。
- 前端测试：vitest + eslint + vue-tsc + build。
- 镜像构建：通过后自动构建并推送至 Docker Hub `akaishuichiw/emby-episode-organizer`（包含 `latest`、版本 tag 及 sha 标签）。

## 架构图

```
下载目录(downloads) ──选择源文件──▶ staging 目录(视频+NFO+封面)
                                     │
                                编辑 NFO / 替换封面
                                     │
                                确认提交(commit)
                                     │
                           移动到 Emby 媒体库 target 目录
```

## 安全说明

- Emby API Key 存储在应用数据库 settings 表，响应时自动脱敏，不落明文配置文件。
- 文件浏览器仅允许访问 `ALLOWED_BROWSE_ROOTS` 配置的白名单目录。
- 整理缓存 (staging) 与媒体库 (target) 路径物理分离，提交前不会触碰 Emby 库。
- 任务删除仅允许在 draft/failed/cancelled 状态下执行，防止误删已入库记录。
