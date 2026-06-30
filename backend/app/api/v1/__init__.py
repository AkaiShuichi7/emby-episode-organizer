"""API v1 总路由。

``api_v1_router`` 是所有 v1 端点的统一入口，子模块（settings / emby /
libraries / series / tasks）通过 ``include_router`` 自挂载。

子模块不在本包主动 import（避免循环引用），改由 ``app.main`` 显式 import
触发各模块底部 ``api_v1_router.include_router(...)`` 调用。
"""

from __future__ import annotations

from fastapi import APIRouter

api_v1_router = APIRouter(prefix="/api/v1")
"""v1 总路由，前缀固定 ``/api/v1``；不直接挂载业务端点，统一在子模块中注册。"""
