<template>
  <section class="page" data-module="driver">
    <header class="page-head">
      <div>
        <h2>司机端 · 我的任务</h2>
        <p class="page-desc">司机按姓名查询派给自己的调度单，在这里接单、完单；状态与调度列表实时一致。</p>
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
        <span>司机姓名</span>
        <input v-model.trim="driver" placeholder="输入调度员派车时填写的司机姓名" />
      </label>
      <button class="btn primary" type="submit">查询我的任务</button>
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
              @click="submitAction(action, row)"
            >
              {{ action }}
            </button>
            <span v-if="!rowActions(row).length" class="muted-text">—</span>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">
            {{ queried ? '暂时没有派给您的任务' : '请先输入司机姓名查询任务' }}
          </td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ rows.length }} 条任务</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      <span v-else-if="successMessage" class="success-text">{{ successMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/truck'
const columns = ["调度单号", "集卡牌号", "作业任务", "计划装卸时间", "派车时间", "返回时间", "调度状态"]

const driver = ref('')
const queried = ref(false)
const rows = ref<Row[]>([])
const errorMessage = ref('')
const successMessage = ref('')

const stats = computed(() => [
  { label: '待接单', value: rows.value.filter((row) => row.status === '已派车').length },
  { label: '作业中', value: rows.value.filter((row) => row.status === '作业中').length },
  { label: '已完成', value: rows.value.filter((row) => row.status === '已完成').length },
])

function rowActions(row: Row): string[] {
  switch (String(row.status ?? '')) {
    case '已派车':
      return ['接单']
    case '作业中':
      return ['完单']
    default:
      return []
  }
}

async function submitAction(action: string, row: Row) {
  errorMessage.value = ''
  successMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action, '司机姓名': driver.value } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message ?? `「${action}」未生效`)
    }
    successMessage.value = payload.message ?? `已${action}`
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '任务操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  successMessage.value = ''
  if (!driver.value) {
    errorMessage.value = '请先填写司机姓名再查询任务'
    return
  }
  try {
    const response = await request(`${ENDPOINT}/driver/tasks?driver=${encodeURIComponent(driver.value)}`)
    const payload = await response.json()
    if (!response.ok) {
      throw new Error(payload.detail ?? '任务列表读取失败')
    }
    rows.value = payload.items ?? []
    queried.value = true
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '任务列表读取失败'
  }
}
</script>
