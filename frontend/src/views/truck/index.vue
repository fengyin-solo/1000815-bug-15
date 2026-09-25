<template>
  <section class="page" data-module="truck">
    <header class="page-head">
      <div>
        <h2>集卡调度管理</h2>
        <p class="page-desc">维护集卡，围绕调度单号、集卡牌号、司机姓名、作业任务做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记集卡</button>
        <RouterLink class="btn" to="/truck/driver">司机端</RouterLink>
        <button class="btn" type="button" @click="exportRows">导出集卡调度清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>调度单号</span>
        <input v-model="keyword" placeholder="按调度单号检索" />
      </label>
      <label class="filter-item">
        <span>调度状态</span>
        <select v-model="statusFilter">
          <option value="">全部</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] || '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actionsFor(row)"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
            <span v-if="!actionsFor(row).length" class="empty-state">—</span>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无集卡调度数据，可先登记集卡</td>
        </tr>
      </tbody>
    </table>

    <div v-if="dispatchTarget" class="modal-mask" @click.self="dispatchTarget = null">
      <div class="modal-card">
        <h3>确认派车 · {{ dispatchTarget.调度单号 }}</h3>
        <div class="form-grid">
          <label class="form-item">
            <span>集卡牌号</span>
            <input :value="dispatchTarget.集卡牌号" disabled />
          </label>
          <label class="form-item">
            <span>司机姓名</span>
            <input v-model="dispatchForm.司机姓名" placeholder="填写本次派车司机" />
          </label>
          <label class="form-item">
            <span>计划装卸时间</span>
            <input v-model="dispatchForm.计划装卸时间" placeholder="如 2026-09-26 08:00" />
          </label>
        </div>
        <p v-if="dispatchError" class="error-text">{{ dispatchError }}</p>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="dispatchTarget = null">取消</button>
          <button class="btn primary" type="button" @click="submitDispatch">确认派车</button>
        </div>
      </div>
    </div>

    <div v-if="createOpen" class="modal-mask" @click.self="createOpen = false">
      <div class="modal-card">
        <h3>登记集卡</h3>
        <div class="form-grid">
          <label v-for="field in createFields" :key="field" class="form-item">
            <span>{{ field }}</span>
            <input v-model="createForm[field]" :placeholder="`填写${field}`" />
          </label>
        </div>
        <p v-if="createError" class="error-text">{{ createError }}</p>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="createOpen = false">取消</button>
          <button class="btn primary" type="button" @click="submitCreate">登记</button>
        </div>
      </div>
    </div>

    <footer class="page-foot">
      <span>共 {{ total }} 条集卡调度记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/truck'
const columns = ["调度单号", "集卡牌号", "司机姓名", "作业任务", "计划装卸时间", "派车时间", "返回时间", "所属车队", "调度状态"]
const statuses = ["待派车", "已派车", "作业中", "已完成", "已取消"]
// 每个状态允许执行的动作，与后端状态机保持一致
const ACTIONS_BY_STATUS: Record<string, string[]> = {
  待派车: ["确认派车", "取消调度"],
  已派车: ["退回", "取消调度"],
  作业中: [],
  已完成: [],
  已取消: [],
}
const createFields = ["调度单号", "集卡牌号", "司机姓名", "作业任务", "计划装卸时间", "所属车队"]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const keyword = ref('')
const statusFilter = ref('')

const dispatchTarget = ref<Row | null>(null)
const dispatchForm = reactive({ 司机姓名: '', 计划装卸时间: '' })
const dispatchError = ref('')

const createOpen = ref(false)
const createForm = reactive<Record<string, string>>({})
const createError = ref('')

const stats = computed(() => {
  const today = new Date().toISOString().slice(0, 10)
  return [
    { label: '待派车任务', value: rows.value.filter((row) => row.status === '待派车').length },
    { label: '作业中集卡', value: rows.value.filter((row) => row.status === '作业中').length },
    { label: '今日派车次数', value: rows.value.filter((row) => String(row.派车时间 ?? '').startsWith(today)).length },
  ]
})

function actionsFor(row: Row): string[] {
  return ACTIONS_BY_STATUS[String(row.status ?? '')] ?? []
}

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  createError.value = ''
  for (const field of createFields) createForm[field] = ''
  createOpen.value = true
}

async function readResult(response: Response): Promise<{ ok: boolean; message: string }> {
  const payload = (await response.json().catch(() => null)) as { ok?: boolean; message?: string; detail?: string } | null
  if (!response.ok || !payload?.ok) {
    throw new Error(payload?.message ?? payload?.detail ?? '集卡调度操作未生效，请稍后重试')
  }
  return { ok: true, message: payload.message ?? '' }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  if (action === '确认派车') {
    dispatchForm.司机姓名 = String(row.司机姓名 ?? '')
    dispatchForm.计划装卸时间 = String(row.计划装卸时间 ?? '')
    dispatchError.value = ''
    dispatchTarget.value = row
    return
  }
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    await readResult(response)
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '集卡调度操作失败'
  }
}

async function submitDispatch() {
  if (!dispatchTarget.value) return
  dispatchError.value = ''
  try {
    const response = await request(`${ENDPOINT}/${dispatchTarget.value.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action: '确认派车', ...dispatchForm } }),
    })
    await readResult(response)
    dispatchTarget.value = null
    await reload()
  } catch (error) {
    dispatchError.value = error instanceof Error ? error.message : '派车失败'
  }
}

async function submitCreate() {
  createError.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: { ...createForm } }),
    })
    await readResult(response)
    createOpen.value = false
    await reload()
  } catch (error) {
    createError.value = error instanceof Error ? error.message : '集卡登记失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (keyword.value) query.set('keyword', keyword.value)
  if (statusFilter.value) query.set('status', statusFilter.value)
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('集卡列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '集卡调度列表读取失败'
  }
}

onMounted(reload)
</script>
