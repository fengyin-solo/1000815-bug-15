<template>
  <section class="page" data-module="truck">
    <header class="page-head">
      <div>
        <h2>集卡调度管理</h2>
        <p class="page-desc">围绕调度单号、集卡牌号、司机姓名做登记、派车与状态流转；派车、接单、完单状态与司机端保持一致。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记调度单</button>
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
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
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
              v-for="action in rowActions(row)"
              :key="action"
              class="link"
              type="button"
              @click="onAction(action, row)"
            >
              {{ action }}
            </button>
            <span v-if="!rowActions(row).length" class="muted-text">—</span>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无集卡调度数据，可先登记调度单</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条集卡调度记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      <span v-else-if="successMessage" class="success-text">{{ successMessage }}</span>
    </footer>

    <div v-if="dispatchRow" class="modal-mask">
      <form class="modal-card" @submit.prevent="submitDispatch">
        <h3>派车 · {{ dispatchRow['调度单号'] }}（{{ dispatchRow['集卡牌号'] }}）</h3>
        <label>
          <span>司机姓名</span>
          <input v-model.trim="dispatchForm['司机姓名']" required placeholder="必填，司机端按此姓名接单" />
        </label>
        <label>
          <span>计划装卸时间</span>
          <input v-model.trim="dispatchForm['计划装卸时间']" required placeholder="如 2026-09-25 09:00" />
        </label>
        <label>
          <span>所属车队</span>
          <input v-model.trim="dispatchForm['所属车队']" placeholder="选填" />
        </label>
        <div class="modal-actions">
          <button class="btn primary" type="submit">确认派车</button>
          <button class="btn ghost" type="button" @click="dispatchRow = null">取消</button>
        </div>
      </form>
    </div>

    <div v-if="createOpen" class="modal-mask">
      <form class="modal-card" @submit.prevent="submitCreate">
        <h3>登记调度单</h3>
        <label>
          <span>调度单号</span>
          <input v-model.trim="createForm['调度单号']" required placeholder="如 TRUC-0004" />
        </label>
        <label>
          <span>集卡牌号</span>
          <input v-model.trim="createForm['集卡牌号']" required placeholder="如 沪D·T1004" />
        </label>
        <label>
          <span>作业任务</span>
          <input v-model.trim="createForm['作业任务']" required placeholder="如 装船作业·CSNU6001234" />
        </label>
        <label>
          <span>司机姓名</span>
          <input v-model.trim="createForm['司机姓名']" placeholder="选填，也可派车时再填" />
        </label>
        <label>
          <span>计划装卸时间</span>
          <input v-model.trim="createForm['计划装卸时间']" placeholder="选填，也可派车时再填" />
        </label>
        <label>
          <span>所属车队</span>
          <input v-model.trim="createForm['所属车队']" placeholder="选填" />
        </label>
        <div class="modal-actions">
          <button class="btn primary" type="submit">确认登记</button>
          <button class="btn ghost" type="button" @click="createOpen = false">取消</button>
        </div>
      </form>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/truck'
const columns = ["调度单号", "集卡牌号", "司机姓名", "作业任务", "计划装卸时间", "派车时间", "返回时间", "所属车队", "调度状态"]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const successMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

const dispatchRow = ref<Row | null>(null)
const dispatchForm = ref<Record<string, string>>({})
const createOpen = ref(false)
const createForm = ref<Record<string, string>>({})

const stats = computed(() => [
  { label: '待派车任务', value: rows.value.filter((row) => row.status === '待派车').length },
  { label: '已派车待接单', value: rows.value.filter((row) => row.status === '已派车').length },
  { label: '作业中集卡', value: rows.value.filter((row) => row.status === '作业中').length },
])

function rowActions(row: Row): string[] {
  switch (String(row.status ?? '')) {
    case '待派车':
      return ['派车', '取消调度']
    case '已派车':
      return ['退回', '取消调度']
    default:
      return []
  }
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  createForm.value = {}
  createOpen.value = true
}

function onAction(action: string, row: Row) {
  if (action === '派车') {
    // 退回后重派：把台账里已填的司机与计划装卸时间带出来，不再让人重填
    dispatchForm.value = {
      '司机姓名': String(row['司机姓名'] ?? ''),
      '计划装卸时间': String(row['计划装卸时间'] ?? ''),
      '所属车队': String(row['所属车队'] ?? ''),
    }
    dispatchRow.value = row
    return
  }
  void submitAction(action, row)
}

async function submitDispatch() {
  const row = dispatchRow.value
  if (!row) return
  const ok = await submitAction('派车', row, { ...dispatchForm.value })
  if (ok) dispatchRow.value = null
}

async function submitCreate() {
  errorMessage.value = ''
  successMessage.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: { ...createForm.value } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message ?? '调度单登记未生效')
    }
    createOpen.value = false
    successMessage.value = payload.message ?? '调度单已登记'
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '调度单登记失败'
  }
}

async function submitAction(action: string, row: Row, extra: Record<string, string> = {}): Promise<boolean> {
  errorMessage.value = ''
  successMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action, ...extra } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message ?? `「${action}」未生效`)
    }
    successMessage.value = payload.message ?? `已${action}`
    await reload()
    return true
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '集卡调度操作失败'
    return false
  }
}

async function reload() {
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
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
