# 后端开发说明

## 环境

- Python 3.12
- 依赖安装：`pip install -e ".[dev]"`

## 常用命令

- 测试：`pytest -v`
- 检查：`ruff check .`
- 类型检查：`mypy .`
- 启动服务：`uvicorn app.main:app --port 8899`

## 健康检查

- `GET /health`
- 返回：`{"status":"ok"}`
