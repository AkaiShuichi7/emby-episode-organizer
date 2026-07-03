# backend

Emby Episode Organizer 后端应用。

## 技术栈

- 语言：Python 3.12
- 框架：FastAPI
- 异步驱动：Uvicorn
- 数据库：SQLAlchemy + aiosqlite
- 数据校验：Pydantic v2
- 图像处理：Pillow

## 目录结构

- `app/api/v1`: API 路由定义
- `app/services`: 核心业务逻辑（Emby 客户端、设置管理、任务处理等）
- `app/db`: 数据库模型与初始化
- `app/schemas`: Pydantic 数据模型
- `app/utils`: 工具类（路径安全、NFO 构建、日志配置等）

## 开发命令

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 启动开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8899

# 运行测试
pytest -v

# 代码风格检查
ruff check .

# 类型检查
mypy .
```

## 接口说明

- API 版本前缀：`/api/v1`
- 健康检查：`GET /health` -> `{"status":"ok"}`
- 自动文档：启动后访问 `/docs` 查看 Swagger UI

## 配置项

参考 `.env.example` 进行配置：
- `DATABASE_URL`: 数据库连接地址
- `LOG_DIR`: 日志存储目录
- `ALLOWED_BROWSE_ROOTS`: 允许文件浏览器访问的根目录列表
- `EMBY_DEFAULT_URL`: 默认 Emby 服务器地址
