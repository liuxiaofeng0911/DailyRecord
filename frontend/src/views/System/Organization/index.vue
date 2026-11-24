<template>
  <div class="page system-page">
    <div class="page-head">
      <h2 class="page-title">组织管理</h2>
      <p class="page-subtitle">MVP 使用默认组织，后续可扩展多组织。</p>
    </div>

    <section class="surface">
      <a-table :columns="columns" :data-source="rows" :loading="loading" row-key="id" size="middle">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="record.status === 'Y' ? 'green' : 'default'">
              {{ record.status === 'Y' ? '启用' : '停用' }}
            </a-tag>
          </template>
        </template>
      </a-table>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'

import { systemApi } from '@/api/api'

const rows = ref([])
const loading = ref(false)

const columns = [
  { title: '组织编码', dataIndex: 'orgCode', key: 'orgCode', width: 160 },
  { title: '组织名称', dataIndex: 'orgName', key: 'orgName' },
  { title: '上级', dataIndex: 'pid', key: 'pid', width: 140 },
  { title: '状态', key: 'status', width: 100 },
]

onMounted(async () => {
  loading.value = true
  try {
    rows.value = (await systemApi.orgTree()) || []
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.system-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
</style>
