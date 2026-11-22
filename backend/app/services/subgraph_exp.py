"""子图探查领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。

另增可复查子图文件交割：把选中邻边、探查种子与扩展深度另存为子图文件，
交接给图谱搜索时按图代核对邻接证据——被移除的边仅可复查、不会复活，
新旧关系不会被拼成一份有效输入。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app import subgraph_repo as repo
from app.graph_state import graph_state
from app.services.base import BaseModuleService
from app.store import store


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _parse_depth(value: Any, default: int = 1) -> int:
    try:
        depth = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return depth if depth > 0 else default


class SubgraphExpService(BaseModuleService):
    MODULE = "subgraph_exp"
    ENTITY = "探查配置"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["配置编号", "探查种子", "扩展策略", "关系过滤", "深度限制", "结果数量", "缓存策略", "上次探查"]
    REQUIRED_FIELDS = ["配置编号", "探查种子", "扩展策略"]
    STATUS_ORDER = ["草稿", "探查中", "已缓存", "已丢弃"]
    ACTION_RULES = {"启动探查": "探查中", "缓存结果": "已缓存", "丢弃缓存": "已丢弃"}
    NEGATIVE_ACTIONS = []

    # ===== 跨模块数据流实现 =====
    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry, message = super().run_action(entry_id, action)
        if entry is None:
            return entry, message
        # 链路 L24: subgraph_exp → graph_search（探查结果更新搜索模板命中）
        if entry.get("status") in ("探查中", "已缓存"):
            search_msg = self._push_to_graph_search(entry)
            message += "；" + search_msg
        # 链路 L25: subgraph_exp → reco_engine（探查种子触发推荐）
        if entry.get("status") in ("探查中", "已缓存"):
            reco_msg = self._push_to_reco_engine(entry)
            message += "；" + reco_msg
        return entry, message

    def _push_to_graph_search(self, entry: dict[str, Any]) -> str:
        rows = store.rows("graph_search")
        next_id = max((int(r.get("id", 0)) for r in rows), default=0) + 1
        gs_entry: dict[str, Any] = {
            "id": next_id,
            "status": "草稿",
            "pending": True,
            "abnormal": False,
            "模板编号": f"GRAP-SUB-{next_id:04d}",
            "搜索类型": "subgraph-traversal",
            "查询语法": str(entry.get("扩展策略", "bfs")),
            "起始实体": str(entry.get("探查种子", "")),
            "关系过滤": str(entry.get("关系过滤", "")),
            "跳数上限": str(entry.get("深度限制", "3")),
            "排序规则": "relevance-desc",
            "使用频次": "0",
        }
        rows.append(gs_entry)
        return f"已生成搜索模板 {gs_entry['模板编号']}"

    def _push_to_reco_engine(self, entry: dict[str, Any]) -> str:
        rows = store.rows("reco_engine")
        next_id = max((int(r.get("id", 0)) for r in rows), default=0) + 1
        reco_entry: dict[str, Any] = {
            "id": next_id,
            "status": "草稿",
            "pending": True,
            "abnormal": False,
            "规则编号": f"RECO-SUB-{next_id:04d}",
            "推荐场景": "子图探查关联推荐",
            "源实体": str(entry.get("探查种子", "")),
            "推荐算法": "subgraph-neighbor-rank",
            "候选数量": int(entry.get("结果数量", 10)),
            "过滤条件": str(entry.get("关系过滤", "")),
            "命中次数": "0",
            "采纳率": "0%",
        }
        rows.append(reco_entry)
        return f"探查种子推送推荐引擎 {reco_entry['规则编号']}"

    # ===== 可复查子图文件：另存、交接、重放、证据附件 =====
    def save_as_file(
        self,
        entry_id: int,
        selected: list[str] | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        """把选中邻边、探查种子与扩展深度另存为可复查子图文件，锚定当前图代。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return None, f"{self.ENTITY} {entry_id} 不存在或已归档"
        seed = str(entry.get("探查种子", "")).strip()
        if not seed:
            return None, "探查配置缺少探查种子，无法另存子图文件"
        depth = _parse_depth(entry.get("深度限制"))
        expansion = graph_state.expand(seed, depth)
        available = {edge["边编号"] for edge in expansion["edges"]}
        if not available:
            return None, f"种子 {seed} 在当前图代 {graph_state.generation} 无生效邻边，无法另存子图文件"
        if selected:
            invalid = [edge_id for edge_id in selected if edge_id not in available]
            if invalid:
                return None, (
                    f"选中邻边 {'、'.join(invalid)} 在当前图代 {graph_state.generation} 不生效，"
                    "新旧关系不能拼成一份有效输入"
                )
            edges = [edge for edge in expansion["edges"] if edge["边编号"] in set(selected)]
        else:
            edges = expansion["edges"]
        file_id = repo.next_file_id()
        record = {
            "id": file_id,
            "文件编号": f"SUBF-{file_id:04d}",
            "来源配置": str(entry.get("配置编号", "")),
            "探查种子": seed,
            "扩展深度": depth,
            "图代": graph_state.generation,
            "邻边清单": [edge["边编号"] for edge in edges],
            "邻边明细": [
                {key: edge[key] for key in ("边编号", "起点", "终点", "关系", "引入图代")}
                for edge in edges
            ],
            "另存时间": _now(),
            "status": "待交接",
            "pending": True,
            "abnormal": False,
        }
        repo.add_file(record)
        return record, (
            f"已另存可复查子图文件 {record['文件编号']}"
            f"（图代 {record['图代']}，邻边 {len(edges)} 条）"
        )

    def list_files(self) -> list[dict[str, Any]]:
        return repo.list_files()

    def get_file(self, file_id: int) -> dict[str, Any] | None:
        return repo.find_file(file_id)

    def handoff_file(self, file_id: int) -> tuple[dict[str, Any] | None, str, bool]:
        """把子图文件交接给图谱搜索：按图代核对邻接证据，写入搜索待办。

        交接按文件幂等：失败后重试找回同一交接记录与同一探查种子，
        已接收的交接重复调用不会重复写入图谱搜索待办。
        """
        file = repo.find_file(file_id)
        if file is None:
            return None, f"子图文件 {file_id} 不存在", False
        existing = repo.find_handoff(file["文件编号"])
        if existing is not None and existing.get("status") == "已接收":
            return existing, (
                f"交接 {existing['交接编号']} 已接收，重试找回同一探查种子 "
                f"{existing['探查种子']}，未重复写入图谱搜索待办"
            ), True
        reconciled, problem = self._reconcile(file)
        if problem is not None:
            handoff = existing or self._new_handoff(file)
            handoff.update({
                "status": "交接失败",
                "失败原因": problem,
                "交接图代": graph_state.generation,
                "交接时间": _now(),
            })
            file["status"] = "交接失败"
            file["abnormal"] = True
            return handoff, (
                f"交接失败：{problem}；探查种子 {file['探查种子']} 已保留在 "
                f"{handoff['交接编号']}，修正后可按同一文件重试"
            ), False
        assert reconciled is not None
        handoff = existing or self._new_handoff(file)
        todo_no = self._push_handoff_to_graph_search(file, handoff, reconciled)
        handoff.update({
            "status": "已接收",
            "失败原因": "",
            "交接图代": graph_state.generation,
            "交接时间": _now(),
            "可导航邻接": reconciled["可导航邻接"],
            "可导航明细": reconciled["可导航明细"],
            "失效复查邻接": reconciled["失效复查邻接"],
            "失效明细": reconciled["失效明细"],
            "新增邻边": reconciled["新增邻边"],
            "检索种子": reconciled["检索种子"],
            "待复查边界": reconciled["待复查边界"],
            "图谱搜索待办": todo_no,
        })
        file["status"] = "已交接"
        file["pending"] = False
        file["abnormal"] = False
        stale_text = "、".join(reconciled["失效复查邻接"]) or "无"
        return handoff, (
            f"交接 {handoff['交接编号']} 已接收：可导航邻接 "
            f"{'、'.join(reconciled['可导航邻接'])} 可直接发动下一次扩展；"
            f"失效复查邻接 {stale_text} 仅复查老调查轨迹；"
            f"图谱搜索待办 {todo_no} 已写入新一轮检索种子与待复查边界"
        ), True

    def replay_file(self, file_id: int) -> tuple[dict[str, Any] | None, str]:
        """重放旧文件片段做核对：被移除的边保持失效，不会重新生效。"""
        file = repo.find_file(file_id)
        if file is None:
            return None, f"子图文件 {file_id} 不存在"
        checks: list[dict[str, Any]] = []
        blocked: list[str] = []
        for edge_id in file["邻边清单"]:
            edge = graph_state.edge(edge_id)
            if edge is None:
                checks.append({"边编号": edge_id, "文件图代状态": "生效", "现图状态": "不存在", "重放生效": False})
                blocked.append(f"{edge_id} 现图不存在，重放不恢复")
                continue
            active = edge["状态"] == "生效"
            checks.append({
                "边编号": edge_id,
                "文件图代状态": "生效",
                "现图状态": "生效" if active else f"已移除@{edge['移除图代']}",
                "重放生效": active,
            })
            if not active:
                blocked.append(f"{edge_id} 已于 {edge['移除图代']} 移除，重放不恢复生效")
        expansion = graph_state.expand(file["探查种子"], int(file["扩展深度"]))
        result = {
            "文件编号": file["文件编号"],
            "探查种子": file["探查种子"],
            "文件图代": file["图代"],
            "重放图代": graph_state.generation,
            "文件边核对": checks,
            "重放拦截": blocked,
            "可导航邻接": [edge["边编号"] for edge in expansion["edges"]],
        }
        if blocked:
            return result, f"重放完成：{len(blocked)} 条被移除边保持失效，未重新生效"
        return result, "重放完成：文件边在当前图代全部生效"

    def evidence_for(self, file_id: int) -> tuple[dict[str, Any] | None, str]:
        """生成当次交接的证据附件：当时的边、关联图代与可扩展邻接组结论。"""
        file = repo.find_file(file_id)
        if file is None:
            return None, f"子图文件 {file_id} 不存在"
        handoff = repo.find_handoff(file["文件编号"])
        if handoff is None or handoff.get("status") != "已接收":
            return None, "文件尚未完成交接，暂无当次证据附件"
        history: list[str] = []
        for item in handoff.get("失效明细", []):
            history.append(
                f"老调查在 {file['图代']} 经 {item['边编号']} 由 {item['起点']} 导航至 "
                f"{item['终点']}；该边因关系规则冲突于 {item['移除图代'] or handoff['交接图代']} "
                f"失效（{item['失效原因']}）"
            )
        navigable_text = "、".join(handoff["可导航邻接"])
        stale_text = "、".join(handoff["失效复查邻接"]) or "无"
        evidence = {
            "文件编号": file["文件编号"],
            "探查种子": file["探查种子"],
            "扩展深度": file["扩展深度"],
            "文件图代": file["图代"],
            "另存时间": file["另存时间"],
            "文件邻边": file["邻边清单"],
            "交接": {
                "交接编号": handoff["交接编号"],
                "交接时图代": handoff["交接图代"],
                "交接时间": handoff["交接时间"],
                "结果": handoff["status"],
            },
            "邻接分组": {
                "可导航邻接组": {
                    "图代": handoff["交接图代"],
                    "边": handoff["可导航明细"],
                    "可直接发动下一次扩展": True,
                },
                "失效复查邻接组": {
                    "边": handoff["失效明细"],
                    "可直接发动下一次扩展": False,
                    "用途": "仅复查老调查轨迹",
                },
            },
            "新增邻边": handoff["新增邻边"],
            "失效邻边": handoff["失效复查邻接"],
            "老调查说明": history,
            "新一轮检索种子": handoff["检索种子"],
            "待复查边界": handoff["待复查边界"],
            "图谱搜索待办": handoff["图谱搜索待办"],
            "结论": (
                f"可导航邻接组（图代 {handoff['交接图代']}：{navigable_text}）"
                f"可直接发动下一次扩展；失效复查邻接组（{stale_text}）仅用于复查，不能发动扩展"
            ),
        }
        return evidence, f"证据附件已生成（{handoff['交接编号']}）"

    def _new_handoff(self, file: dict[str, Any]) -> dict[str, Any]:
        handoff_id = repo.next_handoff_id()
        record = {
            "id": handoff_id,
            "交接编号": f"HAND-{handoff_id:04d}",
            "文件编号": file["文件编号"],
            "探查种子": file["探查种子"],
            "文件图代": file["图代"],
            "交接图代": "",
            "交接时间": "",
            "status": "待交接",
            "失败原因": "",
            "可导航邻接": [],
            "可导航明细": [],
            "失效复查邻接": [],
            "失效明细": [],
            "新增邻边": [],
            "检索种子": [],
            "待复查边界": [],
            "图谱搜索待办": "",
        }
        repo.add_handoff(record)
        return record

    def _reconcile(self, file: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
        """按图代核对文件邻边：分出可导航组与失效复查组，拒绝新旧拼接。"""
        gen_now = graph_state.generation
        seed = str(file["探查种子"])
        depth = int(file["扩展深度"])
        # 文件内部一致性：文件边必须在其图代全部生效，防止新旧关系拼成一份输入
        effective_then = {edge["边编号"] for edge in graph_state.effective_at(file["图代"])}
        mixed = [edge_id for edge_id in file["邻边清单"] if edge_id not in effective_then]
        if mixed:
            return None, (
                f"文件含图代 {file['图代']} 之后引入的边 {'、'.join(mixed)}，"
                "新旧关系不能拼成一份有效输入"
            )
        expansion = graph_state.expand(seed, depth)
        current_edges = expansion["edges"]
        current_ids = [edge["边编号"] for edge in current_edges]
        if not current_ids:
            return None, f"种子 {seed} 在当前图代 {gen_now} 无可导航邻接"
        stale_ids = [edge_id for edge_id in file["邻边清单"] if edge_id not in current_ids]
        stale_detail: list[dict[str, Any]] = []
        for edge_id in stale_ids:
            edge = graph_state.edge(edge_id)
            removed = edge is not None and edge["状态"] == "已移除"
            stale_detail.append({
                "边编号": edge_id,
                "起点": edge["起点"] if edge else "",
                "终点": edge["终点"] if edge else "",
                "关系": edge["关系"] if edge else "",
                "失效原因": "已移除" if removed else "断链不可达",
                "移除图代": edge["移除图代"] if edge else "",
            })
        levels: dict[str, int] = expansion["nodes"]
        max_level = max(levels.values(), default=0)
        next_seeds = sorted(node for node, level in levels.items() if level == max_level and node != seed)
        reachable = set(levels)
        boundary = sorted(
            {point for item in stale_detail for point in (item["起点"], item["终点"])}
            - {seed}
            - reachable
        )
        return {
            "可导航邻接": current_ids,
            "可导航明细": [
                {key: edge[key] for key in ("边编号", "起点", "终点", "关系", "引入图代")}
                for edge in current_edges
            ],
            "失效复查邻接": stale_ids,
            "失效明细": stale_detail,
            "新增邻边": [edge_id for edge_id in current_ids if edge_id not in file["邻边清单"]],
            "检索种子": next_seeds,
            "待复查边界": boundary,
        }, None

    def _push_handoff_to_graph_search(
        self,
        file: dict[str, Any],
        handoff: dict[str, Any],
        reconciled: dict[str, Any],
    ) -> str:
        """接收确认驱动图谱搜索待办：写入新一轮检索种子和待复查边界。"""
        rows = store.rows("graph_search")
        for row in rows:
            if row.get("证据文件") == file["文件编号"]:
                return str(row.get("模板编号", ""))
        next_id = max((int(r.get("id", 0)) for r in rows), default=0) + 1
        relations = sorted({edge["关系"] for edge in reconciled["可导航明细"]})
        todo: dict[str, Any] = {
            "id": next_id,
            "status": "草稿",
            "pending": True,
            "abnormal": False,
            "模板编号": f"GRAP-HAND-{next_id:04d}",
            "搜索类型": "subgraph-handoff",
            "查询语法": f"expand(seed={file['探查种子']},depth={file['扩展深度']},gen={graph_state.generation})",
            "起始实体": ",".join(reconciled["检索种子"]),
            "关系过滤": "、".join(relations),
            "跳数上限": str(file["扩展深度"]),
            "排序规则": "relevance-desc",
            "使用频次": "0",
            "证据文件": file["文件编号"],
            "交接编号": handoff["交接编号"],
            "新一轮检索种子": reconciled["检索种子"],
            "待复查边界": reconciled["待复查边界"],
            "可导航邻接": reconciled["可导航邻接"],
            "失效复查邻接": reconciled["失效复查邻接"],
            "文件图代": file["图代"],
            "当前图代": graph_state.generation,
        }
        rows.append(todo)
        return str(todo["模板编号"])

    def domain_snapshot(self) -> dict[str, Any]:
        base = super().domain_snapshot()
        base["cross_module_consumers"] = ["graph_search", "reco_engine"]
        base["subgraph_files"] = len(repo.list_files())
        return base
