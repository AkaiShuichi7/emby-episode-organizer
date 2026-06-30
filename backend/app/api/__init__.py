"""HTTP API 包。

集中提供 FastAPI 路由层的依赖注入（DB 会话、业务服务）以及按版本号划分
的路由聚合（``app.api.v1``）。后续 T15-T18 任务会向 ``api_v1_router`` 挂
载各自子路由。
"""
