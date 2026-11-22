/** 子图探查文件交割：另存可复查子图文件、交接图谱搜索、重放校验与证据附件下载。 */
import { request } from '@/api/client'
import type {
  FileActionResult,
  GraphStateSnapshot,
  SubgraphFile,
} from '@/data/types'

/** 演示用新关系规则：移除 r7、新增 r9（t→e，依赖）。 */
export const DEMO_RULE_CHANGE = {
  remove: ['r7'],
  add: [{ 边编号: 'r9', 起点: 't', 终点: 'e', 关系: '依赖' }],
  reason: '关系规则冲突：按新规则移除 r7、新增 r9',
}

export async function loadGraphState(): Promise<GraphStateSnapshot> {
  const response = await request('/api/graph/state')
  if (!response.ok) throw new Error('现图状态读取失败')
  return await response.json()
}

export async function evolveGraph(
  payload: typeof DEMO_RULE_CHANGE = DEMO_RULE_CHANGE,
): Promise<{ ok: boolean; message: string }> {
  const response = await request('/api/graph/evolve', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  return await response.json()
}

export async function saveAsSubgraphFile(entryId: number): Promise<FileActionResult> {
  const response = await request(`/api/subgraph_exp/${entryId}/save-as`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
  return await response.json()
}

export async function listSubgraphFiles(): Promise<SubgraphFile[]> {
  const response = await request('/api/subgraph_files')
  if (!response.ok) throw new Error('子图文件读取失败')
  const payload = await response.json()
  return payload.items as SubgraphFile[]
}

export async function handoffSubgraphFile(fileId: number): Promise<FileActionResult> {
  const response = await request(`/api/subgraph_files/${fileId}/handoff`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
  return await response.json()
}

export async function replaySubgraphFile(fileId: number): Promise<FileActionResult> {
  const response = await request(`/api/subgraph_files/${fileId}/replay`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
  return await response.json()
}

export async function downloadSubgraphEvidence(file: SubgraphFile): Promise<void> {
  const response = await request(`/api/subgraph_files/${file.id}/evidence`)
  if (!response.ok) {
    const detail = await response.json().catch(() => null)
    throw new Error(detail?.detail ?? '证据附件下载失败')
  }
  const url = URL.createObjectURL(await response.blob())
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `${file.文件编号}-evidence.json`
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  URL.revokeObjectURL(url)
}
