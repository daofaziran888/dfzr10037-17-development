"""图谱演化领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.graph_state import graph_state
from app.services.base import BaseModuleService
from app.store import store


class GraphEvolveService(BaseModuleService):
    MODULE = "graph_evolve"
    ENTITY = "演化记录"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["记录编号", "变更类型", "影响实体", "影响关系", "版本标签", "变更描述", "回滚版本", "演化时间"]
    REQUIRED_FIELDS = ["记录编号", "变更类型", "影响实体"]
    STATUS_ORDER = ["已记录", "已评审", "已回滚", "已确认"]
    ACTION_RULES = {"提交评审": "已评审", "执行回滚": "已回滚", "确认演化": "已确认"}
    NEGATIVE_ACTIONS = []

    # ===== 跨模块数据流实现 =====
    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry, message = super().run_action(entry_id, action)
        if entry is None:
            return entry, message
        # 链路 L16: graph_evolve → quality_audit（演化记录确认后触发质量审计）
        if entry.get("status") == "已确认":
            audit_msg = self._push_to_quality_audit(entry)
            message += "；" + audit_msg
        # 链路 L17: graph_evolve → graph_compare（演化触发版本比对）
        if entry.get("status") in ("已评审", "已确认"):
            compare_msg = self._push_to_graph_compare(entry)
            message += "；" + compare_msg
        return entry, message

    def _push_to_quality_audit(self, entry: dict[str, Any]) -> str:
        rows = store.rows("quality_audit")
        next_id = max((int(r.get("id", 0)) for r in rows), default=0) + 1
        qa_entry: dict[str, Any] = {
            "id": next_id,
            "status": "待审计",
            "pending": True,
            "abnormal": False,
            "报告编号": f"QUAL-EVOL-{next_id:04d}",
            "审计范围": f"graph_evolution_{entry.get('版本标签','')}",
            "实体准确率": "needs-verification",
            "关系完整率": "needs-verification",
            "冗余度": "post-evolve-check",
            "更新时效": str(entry.get("演化时间", "2026-11-18")),
            "合规结论": "待审计",
            "审计时间": "2026-11-18",
        }
        rows.append(qa_entry)
        return f"已触质量审计 {qa_entry['报告编号']}"

    def _push_to_graph_compare(self, entry: dict[str, Any]) -> str:
        rows = store.rows("graph_compare")
        next_id = max((int(r.get("id", 0)) for r in rows), default=0) + 1
        cmp_entry: dict[str, Any] = {
            "id": next_id,
            "status": "待执行",
            "pending": True,
            "abnormal": False,
            "任务编号": f"GRAP-EVOL-CMP-{next_id:04d}",
            "基准图": str(entry.get("回滚版本", "prev-version")),
            "对比图": str(entry.get("版本标签", "curr-version")),
            "比对维度": "evolution-diff",
            "新增实体": "auto-detected",
            "删除实体": "auto-detected",
            "变更关系": str(entry.get("变更类型", "")),
            "比对时间": str(entry.get("演化时间", "2026-11-18")),
        }
        rows.append(cmp_entry)
        return f"已触发版本比对 {cmp_entry['任务编号']}"

    def domain_snapshot(self) -> dict[str, Any]:
        base = super().domain_snapshot()
        base["cross_module_consumers"] = ["quality_audit", "graph_compare"]
        return base

    # ===== 现图演化：按新关系规则移除旧边、新增新边 =====
    def apply_rule_change(
        self,
        remove: list[str],
        add: list[dict[str, str]],
        reason: str = "",
    ) -> tuple[dict[str, Any] | None, str]:
        """演化现图并留下演化记录，供子图文件交割按图代核对。"""
        result = graph_state.advance(remove, add)
        if not result["ok"]:
            return None, str(result["message"])
        rows = store.rows(self.MODULE)
        next_id = max((int(r.get("id", 0)) for r in rows), default=0) + 1
        changed = result["移除"] + result["新增"]
        entities = sorted({
            point
            for edge_id in changed
            for point in self._edge_endpoints(edge_id)
        })
        record: dict[str, Any] = {
            "id": next_id,
            "status": "已确认",
            "pending": False,
            "abnormal": False,
            "记录编号": f"GRAP-EVOL-{next_id:04d}",
            "变更类型": "关系规则冲突调整",
            "影响实体": "、".join(entities) or "-",
            "影响关系": f"移除 {'、'.join(result['移除']) or '无'}；新增 {'、'.join(result['新增']) or '无'}",
            "版本标签": result["图代"],
            "变更描述": reason or "按新关系规则调整现图",
            "回滚版本": result["上一图代"],
            "演化时间": datetime.now().strftime("%Y-%m-%d"),
        }
        rows.append(record)
        result["演化记录"] = record["记录编号"]
        return result, f"现图已演化至 {result['图代']}，演化记录 {record['记录编号']} 已登记"

    @staticmethod
    def _edge_endpoints(edge_id: str) -> tuple[str, ...]:
        edge = graph_state.edge(edge_id)
        if edge is None:
            return ()
        return (str(edge["起点"]), str(edge["终点"]))