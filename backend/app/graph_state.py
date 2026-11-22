"""现图状态：图代、边生命周期与演化操作。

子图探查另存的可复查子图文件以图代为锚点核对邻接证据。文件交割期间
现图可能按新关系规则演化（移除旧边、新增新边），这里记录每条边的
引入/移除图代，保证旧文件可复查、被移除的边不会在重放时复活。
"""
from __future__ import annotations

from typing import Any

GENERATION_PREFIX = "GEN-2026-"


class GraphState:
    """内存版现图：真实项目里会换成图数据库访问层。"""

    def __init__(self) -> None:
        self._seq = 1
        self._edges: list[dict[str, Any]] = [
            self._edge("r1", "a", "b", "属于"),
            self._edge("r5", "t", "m", "引用"),
            self._edge("r6", "t", "n", "引用"),
            self._edge("r7", "t", "c", "依赖"),
            self._edge("r8", "c", "d", "依赖"),
        ]

    def _edge(
        self,
        edge_id: str,
        source: str,
        target: str,
        relation: str,
        introduced: str | None = None,
    ) -> dict[str, Any]:
        return {
            "边编号": edge_id,
            "起点": source,
            "终点": target,
            "关系": relation,
            "引入图代": introduced or self.generation,
            "移除图代": "",
            "状态": "生效",
        }

    @property
    def generation(self) -> str:
        return f"{GENERATION_PREFIX}{self._seq:03d}"

    @staticmethod
    def _gen_num(generation: str) -> int:
        try:
            return int(str(generation).rsplit("-", 1)[1])
        except (IndexError, ValueError):
            return 0

    def edge(self, edge_id: str) -> dict[str, Any] | None:
        for edge in self._edges:
            if edge["边编号"] == edge_id:
                return edge
        return None

    def active_edges(self) -> list[dict[str, Any]]:
        return [dict(edge) for edge in self._edges if edge["状态"] == "生效"]

    def removed_edges(self) -> list[dict[str, Any]]:
        return [dict(edge) for edge in self._edges if edge["状态"] == "已移除"]

    def effective_at(self, generation: str) -> list[dict[str, Any]]:
        """重建指定图代的生效边：引入不晚于该图代，且移除图代晚于该图代。"""
        gen = self._gen_num(generation)
        result: list[dict[str, Any]] = []
        for edge in self._edges:
            introduced = self._gen_num(edge["引入图代"])
            removed = self._gen_num(edge["移除图代"]) if edge["移除图代"] else 0
            if introduced <= gen and (not removed or removed > gen):
                result.append(dict(edge))
        return result

    def expand(self, seed: str, depth: int, generation: str | None = None) -> dict[str, Any]:
        """从种子出发按深度分层扩展（默认取当前图代），返回生效邻边与节点层级。"""
        edges = self.effective_at(generation or self.generation)
        levels: dict[str, int] = {seed: 0}
        used: list[dict[str, Any]] = []
        used_ids: set[str] = set()
        frontier = [seed]
        for level in range(1, max(int(depth), 0) + 1):
            next_frontier: list[str] = []
            for edge in edges:
                if edge["边编号"] in used_ids:
                    continue
                if edge["起点"] in frontier:
                    node = edge["终点"]
                elif edge["终点"] in frontier:
                    node = edge["起点"]
                else:
                    continue
                used_ids.add(edge["边编号"])
                used.append(edge)
                if node not in levels:
                    levels[node] = level
                    next_frontier.append(node)
            frontier = next_frontier
        return {"nodes": levels, "edges": [dict(edge) for edge in used]}

    def advance(
        self,
        remove: list[str],
        add: list[dict[str, str]],
    ) -> dict[str, Any]:
        """按新关系规则演化现图：移除旧边、新增新边，图代递进一代。"""
        previous = self.generation
        next_gen = f"{GENERATION_PREFIX}{self._seq + 1:03d}"
        removed: list[str] = []
        added: list[str] = []
        skipped: list[str] = []
        for edge_id in remove:
            edge = self.edge(edge_id)
            if edge is None:
                skipped.append(f"{edge_id} 不存在")
                continue
            if edge["状态"] == "已移除":
                skipped.append(f"{edge_id} 已移除")
                continue
            edge["状态"] = "已移除"
            edge["移除图代"] = next_gen
            removed.append(edge_id)
        for spec in add:
            edge_id = str(spec.get("边编号", "")).strip()
            source = str(spec.get("起点", "")).strip()
            target = str(spec.get("终点", "")).strip()
            relation = str(spec.get("关系", "")).strip() or "关联"
            if not edge_id or not source or not target:
                skipped.append("新增边缺少边编号/起点/终点")
                continue
            if self.edge(edge_id) is not None:
                skipped.append(f"{edge_id} 已存在")
                continue
            self._edges.append(self._edge(edge_id, source, target, relation, introduced=next_gen))
            added.append(edge_id)
        if not removed and not added:
            return {
                "ok": False,
                "message": f"现图已处于新规则（{previous}），无待应用变更",
                "图代": previous,
                "上一图代": previous,
                "移除": [],
                "新增": [],
                "跳过": skipped,
            }
        self._seq += 1
        return {
            "ok": True,
            "message": f"现图已演化至 {next_gen}",
            "图代": next_gen,
            "上一图代": previous,
            "移除": removed,
            "新增": added,
            "跳过": skipped,
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "图代": self.generation,
            "生效边": self.active_edges(),
            "已移除边": self.removed_edges(),
        }


graph_state = GraphState()
