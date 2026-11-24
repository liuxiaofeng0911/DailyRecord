<template>
  <div class="page account-page">
    <div class="row-between page-head">
      <div>
        <h2 class="page-title">账户设置</h2>
        <p class="page-subtitle">管理密码、登录设备与数据导出。</p>
      </div>
      <a-button @click="pwdOpen = true">修改密码</a-button>
    </div>

    <section class="surface">
      <div class="row-between section-head">
        <strong>账户信息</strong>
        <span class="chip">{{ roleLabel }}</span>
      </div>
      <a-descriptions :column="2" bordered size="small">
        <a-descriptions-item label="登录账号">{{ user.userid }}</a-descriptions-item>
        <a-descriptions-item label="显示名">{{ user.username }}</a-descriptions-item>
        <a-descriptions-item label="邮箱">{{ user.email }}</a-descriptions-item>
        <a-descriptions-item label="角色">{{ roleLabel }}</a-descriptions-item>
      </a-descriptions>
    </section>

    <section class="surface">
      <div class="row-between section-head">
        <strong>登录设备</strong>
        <a-button size="small" danger @click="revokeAll">退出全部设备</a-button>
      </div>
      <a-spin :spinning="sessionLoading">
        <a-table
          :columns="sessionColumns"
          :data-source="sessions"
          :pagination="false"
          row-key="id"
          size="small"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'device'">
              <span>{{ record.userAgent }}</span>
              <a-tag v-if="record.current" color="blue" style="margin-left: 6px">当前</a-tag>
            </template>
            <template v-else-if="column.key === 'action'">
              <a-button
                v-if="!record.current"
                size="small"
                danger
                type="link"
                @click="revokeSession(record)"
              >
                撤销
              </a-button>
            </template>
          </template>
        </a-table>
      </a-spin>
    </section>

    <section class="surface">
      <div class="section-head">
        <strong>导出数据</strong>
        <p class="muted export-hint">导出全部记录为 JSON 或 Markdown，便于备份与迁移。</p>
      </div>
      <a-space>
        <a-button :loading="exporting === 'json'" @click="doExport('json')">导出 JSON</a-button>
        <a-button :loading="exporting === 'markdown'" @click="doExport('markdown')">导出 Markdown</a-button>
      </a-space>
    </section>

    <EditPwdModal v-model:open="pwdOpen" />
  </div>
</template>

<script setup>
import { Modal, message } from 'antdv-next'
import { computed, onMounted, ref } from 'vue'
import { useStore } from 'vuex'

import { authApi, exportApi } from '@/api/api'
import EditPwdModal from '@/components/EditPwdModal.vue'
import { downloadText } from '@/utils'

const store = useStore()
const pwdOpen = ref(false)
const sessions = ref([])
const sessionLoading = ref(false)
const exporting = ref('')

const user = computed(() => store.state.auth.userInfo || {})
const roleLabel = computed(() => (user.value.roleCode === 'OWNER' ? '所有者' : '成员'))

const sessionColumns = [
  { title: '设备', key: 'device', ellipsis: true },
  { title: 'IP', dataIndex: 'ip', key: 'ip', width: 130 },
  { title: '最近活跃', dataIndex: 'lastSeenAt', key: 'lastSeenAt', width: 170 },
  { title: '创建时间', dataIndex: 'createdAt', key: 'createdAt', width: 170 },
  { title: '操作', key: 'action', width: 90 },
]

async function loadSessions() {
  sessionLoading.value = true
  try {
    sessions.value = (await authApi.sessions()) || []
  } finally {
    sessionLoading.value = false
  }
}

async function revokeSession(record) {
  await authApi.revokeSession(record.id)
  message.success('已撤销该设备')
  loadSessions()
}

function revokeAll() {
  Modal.confirm({
    title: '退出全部设备？',
    content: '当前设备也会退出，需要重新登录。',
    okText: '确认退出',
    okType: 'danger',
    onOk: async () => {
      await authApi.revokeAll()
      await store.dispatch('auth/clear')
      window.location.hash = '#/Login'
    },
  })
}

async function doExport(format) {
  exporting.value = format
  try {
    const data = await exportApi.run({ format })
    downloadText(data.filename, data.content, data.mimeType)
    message.success(`已导出 ${data.count} 条记录`)
  } finally {
    exporting.value = ''
  }
}

onMounted(loadSessions)
</script>

<style scoped lang="less">
.account-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-head {
  margin-bottom: 14px;
}

.export-hint {
  margin: 6px 0 0;
  font-size: 12px;
}
</style>
