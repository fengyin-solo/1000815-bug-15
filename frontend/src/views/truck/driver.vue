<template>
  <section class="page" data-module="truck-driver">
    <header class="page-head">
      <div>
        <h2>集卡司机端</h2>
        <p class="page-desc">司机按姓名查看派给自己的活；接单、完单后状态与调度列表实时一致。</p>
      </div>
      <RouterLink class="btn" to="/truck">返回调度列表</RouterLink>
    </header>

    <form class="filter-bar" @submit.prevent="loadJobs">
      <label class="filter-item">
        <span>司机姓名</span>
        <input v-model="driver" placeholder="输入司机姓名查询" />
      </label>
      <button class="btn" type="submit">查询我的活</button>
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
        <tr v-if="queried && !rows.length">
          <td :colspan="columns.length + 1" class="empty-state">当前没有派给「{{ lastDriver }}」的活</td>
        </tr>
        <tr v-if="!queried">
          <td :colspan="columns.length + 1" class="empty-state">请先输入司机姓名查询</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ rows.length }} 条派车记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/truck'
const columns = ["调度单号", "集卡牌号", "作业任务", "计划装卸时间", "派车时间", "调度状态"]
// 司机侧只接活、完单；派车与退回在调度列表操作
const ACTIONS_BY_STATUS: Record<string, string[]> = {
  已派车: ["司机接单"],
  作业中: ["确认完单"],
}

const driver = ref('')
const lastDriver = ref('')
const rows = ref<Row[]>([])
const queried = ref(false)
const errorMessage = ref('')

function actionsFor(row: Row): string[] {
  return ACTIONS_BY_STATUS[String(row.status ?? '')] ?? []
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = (await response.json().catch(() => null)) as { ok?: boolean; message?: string } | null
    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.message ?? '操作未生效，请稍后重试')
    }
    await loadJobs()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '操作失败'
  }
}

async function loadJobs() {
  errorMessage.value = ''
  const name = driver.value.trim()
  if (!name) {
    errorMessage.value = '请先填写司机姓名'
    return
  }
  try {
    const response = await request(`${ENDPOINT}/driver?driver=${encodeURIComponent(name)}`)
    const payload = (await response.json().catch(() => null)) as { items?: Row[]; detail?: string } | null
    if (!response.ok) {
      throw new Error(payload?.detail ?? '司机任务读取失败')
    }
    rows.value = payload?.items ?? []
    lastDriver.value = name
    queried.value = true
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '司机任务读取失败'
  }
}
</script>
