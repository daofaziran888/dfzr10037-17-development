<template>
  <section class="page" :data-module="meta.key">
    <header class="page-head">
      <div>
        <h2>{{ meta.name }}</h2>
        <p class="page-desc">{{ meta.desc }}</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" data-testid="open-create" type="button" @click="openCreate">
          登记{{ meta.entity }}
        </button>
        <button class="btn" data-testid="export" type="button" @click="exportRows">
          导出{{ meta.name }}清单
        </button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <p class="status-legend">
      <span v-for="item in statusSummary" :key="item.status" class="legend-item">
        {{ item.status }}：{{ item.count }}
      </span>
    </p>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :data-testid="`filter-${field}`" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" data-testid="query" type="submit">查询</button>
      <button class="btn ghost" data-testid="reset" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in meta.fields" :key="column">{{ column }}</th>
          <th>当前状态</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)" :data-testid="`row-${row.id}`" :data-status="String(row.status)">
          <td v-for="column in meta.fields" :key="column">{{ row[column] ?? '—' }}</td>
          <td>{{ row.status }}</td>
          <td class="row-actions">
            <button
              v-for="action in meta.actions"
              :key="action"
              class="link"
              type="button"
              :data-testid="`action-${row.id}-${action}`"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
            <button
              v-if="meta.key === 'subgraph_exp'"
              class="link"
              type="button"
              :data-testid="`save-as-${row.id}`"
              @click="saveAsFile(row)"
            >
              另存子图文件
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="meta.fields.length + 2" class="empty-state">
            暂无{{ meta.name }}数据，可先登记{{ meta.entity }}
          </td>
        </tr>
      </tbody>
    </table>

    <section v-if="meta.key === 'subgraph_exp'" class="subgraph-file-panel" data-testid="subgraph-file-panel">
      <h3>可复查子图文件</h3>
      <p class="graph-state-line" data-testid="graph-state">
        <span>现图图代：{{ graphState?.图代 ?? '—' }}</span>
        <span>生效边：{{ edgeText(graphState?.生效边) }}</span>
        <span>已移除：{{ edgeText(graphState?.已移除边) }}</span>
        <button class="btn" data-testid="evolve-graph" type="button" @click="evolveCurrentGraph">
          应用新关系规则（移除 r7、新增 r9）
        </button>
      </p>
      <table class="data-table">
        <thead>
          <tr>
            <th>文件编号</th>
            <th>探查种子</th>
            <th>扩展深度</th>
            <th>邻边清单</th>
            <th>图代</th>
            <th>状态</th>
            <th>交割操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="file in subgraphFiles" :key="file.id" :data-testid="`file-${file.id}`">
            <td>{{ file.文件编号 }}</td>
            <td>{{ file.探查种子 }}</td>
            <td>{{ file.扩展深度 }}</td>
            <td>{{ file.邻边清单.join('、') }}</td>
            <td>{{ file.图代 }}</td>
            <td>{{ file.status }}</td>
            <td class="row-actions">
              <button class="link" type="button" :data-testid="`handoff-${file.id}`" @click="handoffFile(file)">
                交接图谱搜索
              </button>
              <button class="link" type="button" :data-testid="`replay-${file.id}`" @click="replayFile(file)">
                重放校验
              </button>
              <button class="link" type="button" :data-testid="`evidence-${file.id}`" @click="downloadEvidence(file)">
                下载证据附件
              </button>
            </td>
          </tr>
          <tr v-if="!subgraphFiles.length">
            <td colspan="7" class="empty-state">暂无可复查子图文件，可在上方探查配置行另存</td>
          </tr>
        </tbody>
      </table>
      <pre v-if="fileMessage" class="file-message" data-testid="file-message">{{ fileMessage }}</pre>
    </section>

    <div v-if="showCreate" class="modal-backdrop" data-testid="create-modal">
      <form class="modal" @submit.prevent="submitCreate">
        <h3>登记{{ meta.entity }}</h3>
        <label v-for="field in meta.fields" :key="field" class="create-field">
          <span>{{ field }}</span>
          <input v-model="createValues[field]" :data-testid="`create-${field}`" required />
        </label>
        <div class="page-actions">
          <button class="btn" type="button" @click="showCreate = false">取消</button>
          <button class="btn primary" data-testid="submit-create" type="submit" :disabled="creating">
            {{ creating ? '提交中…' : '确认登记' }}
          </button>
        </div>
      </form>
    </div>

    <footer class="page-foot">
      <span>共 {{ total }} 条{{ meta.name }}记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import {
  createEntry,
  downloadEntries,
  listEntries,
  moduleMeta,
  runAction as applyAction,
} from '@/api/backend-service'
import {
  downloadSubgraphEvidence,
  evolveGraph,
  handoffSubgraphFile,
  listSubgraphFiles,
  loadGraphState,
  replaySubgraphFile,
  saveAsSubgraphFile,
} from '@/domain/subgraph_exp'
import type { EntryRow, GraphEdge, GraphStateSnapshot, SubgraphFile } from '@/data/types'

const props = defineProps<{ moduleKey: string }>()
const meta = moduleMeta(props.moduleKey)
const rows = ref<EntryRow[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = meta.fields.slice(0, 3)
const showCreate = ref(false)
const creating = ref(false)
const createValues = ref<Record<string, string>>({})
const stats = computed(() => [
  { label: meta.metrics[0], value: total.value },
  { label: meta.metrics[1], value: rows.value.filter((row) => row.status === meta.statuses[1]).length },
  {
    label: meta.metrics[2],
    value: rows.value.filter((row) => row.status === meta.statuses[meta.statuses.length - 1]).length,
  },
])
const statusSummary = computed(() =>
  meta.statuses.map((status) => ({
    status,
    count: rows.value.filter((row) => String(row.status) === status).length,
  })),
)

function resetFilters() {
  filters.value = {}
  void reload()
}

async function exportRows() {
  errorMessage.value = ''
  try {
    await downloadEntries(meta.key, filters.value)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '导出失败'
  }
}

function openCreate() {
  createValues.value = Object.fromEntries(meta.fields.map((field) => [field, '']))
  errorMessage.value = ''
  showCreate.value = true
}

async function submitCreate() {
  creating.value = true
  errorMessage.value = ''
  try {
    const result = await createEntry(meta.key, createValues.value)
    if (!result.ok) throw new Error(result.message)
    showCreate.value = false
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '登记失败'
  } finally {
    creating.value = false
  }
}

async function runAction(action: string, row: EntryRow) {
  errorMessage.value = ''
  try {
    const result = await applyAction(meta.key, Number(row.id), action)
    if (!result.ok) throw new Error(result.message)
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  try {
    const payload = await listEntries(meta.key, filters.value)
    rows.value = payload.items
    total.value = payload.total
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '业务列表读取失败'
  }
}

// ===== 子图探查：可复查子图文件交割 =====
const isSubgraphExp = meta.key === 'subgraph_exp'
const graphState = ref<GraphStateSnapshot | null>(null)
const subgraphFiles = ref<SubgraphFile[]>([])
const fileMessage = ref('')

function edgeText(edges: GraphEdge[] | undefined): string {
  if (!edges || !edges.length) return '无'
  return edges.map((edge) => edge.边编号).join('、')
}

async function refreshSubgraphPanel() {
  if (!isSubgraphExp) return
  try {
    const [state, files] = await Promise.all([loadGraphState(), listSubgraphFiles()])
    graphState.value = state
    subgraphFiles.value = files
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '子图文件读取失败'
  }
}

async function saveAsFile(row: EntryRow) {
  errorMessage.value = ''
  fileMessage.value = ''
  try {
    const result = await saveAsSubgraphFile(Number(row.id))
    if (!result.ok) throw new Error(result.message)
    fileMessage.value = result.message
    await refreshSubgraphPanel()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '另存子图文件失败'
  }
}

async function evolveCurrentGraph() {
  errorMessage.value = ''
  fileMessage.value = ''
  try {
    const result = await evolveGraph()
    fileMessage.value = result.message
    await refreshSubgraphPanel()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '现图演化失败'
  }
}

async function handoffFile(file: SubgraphFile) {
  errorMessage.value = ''
  fileMessage.value = ''
  try {
    const result = await handoffSubgraphFile(file.id)
    const handoff = result.handoff
    const lines = [result.message]
    if (result.ok && handoff) {
      lines.push(`可导航邻接组：${handoff.可导航邻接.join('、') || '无'}（可直接发动下一次扩展）`)
      lines.push(`失效复查邻接组：${handoff.失效复查邻接.join('、') || '无'}（仅复查）`)
      lines.push(`新一轮检索种子：${handoff.检索种子.join('、') || '无'}`)
      lines.push(`待复查边界：${handoff.待复查边界.join('、') || '无'}`)
      lines.push(`图谱搜索待办：${handoff.图谱搜索待办 || '无'}`)
    }
    fileMessage.value = lines.join('\n')
    if (!result.ok) errorMessage.value = result.message
    await refreshSubgraphPanel()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '交接失败'
  }
}

async function replayFile(file: SubgraphFile) {
  errorMessage.value = ''
  fileMessage.value = ''
  try {
    const result = await replaySubgraphFile(file.id)
    const replay = result.replay
    const lines = [result.message]
    if (replay) {
      for (const check of replay.文件边核对) {
        lines.push(
          `边 ${check.边编号}：文件图代状态 ${check.文件图代状态}，现图状态 ${check.现图状态}，重放生效 ${check.重放生效 ? '是' : '否'}`,
        )
      }
      if (replay.重放拦截.length) lines.push(`重放拦截：${replay.重放拦截.join('；')}`)
      lines.push(`当前可导航邻接：${replay.可导航邻接.join('、') || '无'}`)
    }
    fileMessage.value = lines.join('\n')
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '重放校验失败'
  }
}

async function downloadEvidence(file: SubgraphFile) {
  errorMessage.value = ''
  try {
    await downloadSubgraphEvidence(file)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '证据附件下载失败'
  }
}

onMounted(() => {
  void reload()
  void refreshSubgraphPanel()
})
</script>
