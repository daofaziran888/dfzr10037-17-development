"""业务路由汇总：所有模块共用一套资源路由，由领域服务完成分派。"""
from __future__ import annotations

from app.routers import resource, subgraph_files

# 子图文件交割路由含 /api/subgraph_files 等固定路径，
# 必须先于通用资源路由注册，避免被 /api/{module} 动态段抢占。
ROUTERS = [subgraph_files, resource]
