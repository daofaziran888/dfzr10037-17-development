"""子图文件交割接口：现图状态、另存可复查子图文件、交接、重放与证据附件下载。

路由需先于通用资源路由注册，避免 /api/subgraph_files 被当成业务模块 key。
业务判断都在领域服务里，路由层只做分派。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.graph_state import graph_state
from app.schemas import EvolvePayload, SaveAsPayload
from app.services import service_for
from app.services.graph_evolve import GraphEvolveService
from app.services.subgraph_exp import SubgraphExpService

router = APIRouter(prefix="/api", tags=["子图文件交割"])


def _subgraph_service() -> SubgraphExpService:
    service = service_for("subgraph_exp")
    if not isinstance(service, SubgraphExpService):
        raise HTTPException(status_code=500, detail="子图探查服务未就绪")
    return service


def _evolve_service() -> GraphEvolveService:
    service = service_for("graph_evolve")
    if not isinstance(service, GraphEvolveService):
        raise HTTPException(status_code=500, detail="图谱演化服务未就绪")
    return service


@router.get("/graph/state")
def graph_state_snapshot() -> dict[str, Any]:
    """现图快照：当前图代、生效边与已移除边。"""
    return graph_state.snapshot()


@router.post("/graph/evolve")
def evolve_graph(payload: EvolvePayload) -> dict[str, Any]:
    """按新关系规则演化现图（如移除 r7、新增 r9），图代递进一代。"""
    result, message = _evolve_service().apply_rule_change(
        payload.remove, payload.add, payload.reason.strip())
    return {"ok": result is not None, "message": message, "result": result}


@router.post("/subgraph_exp/{entry_id}/save-as")
def save_as_file(entry_id: int, payload: SaveAsPayload | None = None) -> dict[str, Any]:
    """把选中邻边、探查种子与扩展深度另存为可复查子图文件。"""
    selected = payload.edges if payload else None
    record, message = _subgraph_service().save_as_file(entry_id, selected)
    return {"ok": record is not None, "message": message, "file": record}


@router.get("/subgraph_files")
def list_files() -> dict[str, Any]:
    items = _subgraph_service().list_files()
    return {"items": items, "total": len(items)}


@router.get("/subgraph_files/{file_id}")
def file_detail(file_id: int) -> dict[str, Any]:
    record = _subgraph_service().get_file(file_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"子图文件 {file_id} 不存在")
    return record


@router.post("/subgraph_files/{file_id}/handoff")
def handoff_file(file_id: int) -> dict[str, Any]:
    """交接子图文件给图谱搜索：按图代核对邻接证据，写入搜索待办。"""
    handoff, message, ok = _subgraph_service().handoff_file(file_id)
    if handoff is None:
        raise HTTPException(status_code=404, detail=message)
    return {"ok": ok, "message": message, "handoff": handoff}


@router.post("/subgraph_files/{file_id}/replay")
def replay_file(file_id: int) -> dict[str, Any]:
    """重放旧文件片段做核对：被移除的边保持失效，不会重新生效。"""
    result, message = _subgraph_service().replay_file(file_id)
    if result is None:
        raise HTTPException(status_code=404, detail=message)
    return {"ok": True, "message": message, "replay": result}


@router.get("/subgraph_files/{file_id}/evidence")
def download_evidence(file_id: int) -> JSONResponse:
    """下载当次交接的证据附件：当时的边、关联图代与可扩展邻接组结论。"""
    evidence, message = _subgraph_service().evidence_for(file_id)
    if evidence is None:
        raise HTTPException(status_code=409, detail=message)
    filename = f"{evidence['文件编号']}-{evidence['交接']['交接编号']}-evidence.json"
    return JSONResponse(
        content=evidence,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        media_type="application/json; charset=utf-8",
    )
