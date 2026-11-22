/** 纯前端数据层的公共类型：与全栈版后端返回的结构保持一致，换回后端时页面不用改。 */

export type EntryRow = {
  id: number
  status: string
  pending: boolean
  abnormal: boolean
  [field: string]: string | number | boolean
}

export type ModuleMeta = {
  key: string
  name: string
  entity: string
  desc: string
  fields: string[]
  statuses: string[]
  actions: string[]
  actionTargets: Record<string, string>
  metrics: string[]
}

export type PageResult = {
  items: EntryRow[]
  total: number
  page: number
  size: number
}

export type ActionResult = {
  ok: boolean
  message: string
}

export type OverviewResult = {
  cards: { label: string; value: number }[]
  modules: { name: string; created: number; pending: number; abnormal: number }[]
}

/** 现图边：带引入/移除图代的生命周期信息。 */
export type GraphEdge = {
  边编号: string
  起点: string
  终点: string
  关系: string
  引入图代: string
  移除图代: string
  状态: string
}

export type GraphStateSnapshot = {
  图代: string
  生效边: GraphEdge[]
  已移除边: GraphEdge[]
}

/** 可复查子图文件：选中邻边、探查种子与扩展深度的另存产物。 */
export type SubgraphFile = {
  id: number
  文件编号: string
  来源配置: string
  探查种子: string
  扩展深度: number
  图代: string
  邻边清单: string[]
  邻边明细: GraphEdge[]
  另存时间: string
  status: string
}

export type HandoffRecord = {
  id: number
  交接编号: string
  文件编号: string
  探查种子: string
  文件图代: string
  交接图代: string
  交接时间: string
  status: string
  失败原因: string
  可导航邻接: string[]
  失效复查邻接: string[]
  新增邻边: string[]
  检索种子: string[]
  待复查边界: string[]
  图谱搜索待办: string
}

export type ReplayCheck = {
  边编号: string
  文件图代状态: string
  现图状态: string
  重放生效: boolean
}

export type ReplayResult = {
  文件编号: string
  探查种子: string
  文件图代: string
  重放图代: string
  文件边核对: ReplayCheck[]
  重放拦截: string[]
  可导航邻接: string[]
}

export type FileActionResult = {
  ok: boolean
  message: string
  file?: SubgraphFile
  handoff?: HandoffRecord
  replay?: ReplayResult
}
