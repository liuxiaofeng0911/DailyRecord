<template>
  <div class="page account-page">
    <div class="row-between page-head">
      <div>
        <h2 class="page-title">账户设置</h2>
        <p class="page-subtitle">管理账号、照片库与数据导出。</p>
      </div>
      <a-tooltip title="修改当前账号的登录密码">
        <a-button @click="pwdOpen = true">修改密码</a-button>
      </a-tooltip>
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
        <a-descriptions-item label="版本">{{ appVersion }}</a-descriptions-item>
      </a-descriptions>
    </section>

    <section class="surface">
      <div class="row-between section-head">
        <strong>照片库</strong>
        <div class="photo-head">
          <a-tag :color="photoTagColor">{{ photoTagText }}</a-tag>
          <a-tooltip title="重新尝试为当前账号开通照片库">
            <a-button
              v-if="photoCanRetry"
              size="small"
              :loading="photoRetrying"
              @click="retryPhoto"
            >
              重试开通
            </a-button>
          </a-tooltip>
        </div>
      </div>
      <p class="muted info-text">{{ photoDetail }}</p>
      <p class="muted info-text">
        照片库是独立部署的照片服务，需要管理员在服务器配置；普通账号无需单独开通。
      </p>
    </section>

    <section class="surface">
      <div class="row-between section-head">
        <strong>登录设备</strong>
        <a-tooltip title="撤销所有设备的登录状态，当前设备也会退出">
          <a-button size="small" danger @click="revokeAll">退出全部设备</a-button>
        </a-tooltip>
      </div>
      <a-spin :spinning="sessionLoading">
        <a-table
          :columns="sessionColumns"
          :data-source="sessions"
          :pagination="false"
          row-key="id"
          size="small"
          :scroll="{ x: 860 }"
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
      <div class="row-between section-head">
        <strong>标签图标</strong>
        <span class="muted tag-hint">自动匹配，可手动覆盖</span>
      </div>
      <a-spin :spinning="tagLoading">
        <div v-if="tags.length" class="tag-icon-list">
          <div v-for="tag in tags" :key="tag.id" class="tag-icon-row">
            <span class="tag-icon-name">
              <AppIcon :name="resolveTagIcon(tag.name, tag.icon)" :size="16" />
              {{ tag.name }}
            </span>
            <a-select
              :value="tag.icon || resolveTagIcon(tag.name)"
              :options="tagOptions(tag)"
              style="width: 180px"
              @change="saveTagIcon(tag, $event)"
            >
              <template #option="{ value }">
                <span class="icon-option">
                  <AppIcon :name="value" :size="16" />
                  {{ iconLabel(value) }}
                </span>
              </template>
            </a-select>
          </div>
        </div>
        <a-empty v-else description="保存带标签的记录后，可在这里调整图标" />
      </a-spin>
    </section>

    <section class="surface">
      <div class="row-between section-head">
        <strong>照片回收站</strong>
        <a-tooltip :title="`查看已删除的照片，保留 ${trashKeepDays} 天`">
          <a-button size="small" @click="trashOpen = true">打开回收站</a-button>
        </a-tooltip>
      </div>
      <p class="muted trash-hint">
        删除的照片保留 {{ trashKeepDays }} 天，期间可恢复；到期自动清理。
      </p>
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
    <TrashDrawer v-model:open="trashOpen" @changed="onTrashChanged" />
  </div>
</template>

<script setup>
import { Modal, message } from 'antdv-next'
import { computed, onMounted, ref } from 'vue'
import { useStore } from 'vuex'

import { authApi, exportApi, immichApi, tagApi } from '@/api/api'
import AppIcon from '@/components/AppIcon.vue'
import EditPwdModal from '@/components/EditPwdModal.vue'
import TrashDrawer from '@/components/TrashDrawer.vue'
import { TAG_ICON_OPTIONS, resolveTagIcon } from '@/store/icon'
import { downloadText } from '@/utils'

const store = useStore()
const appVersion = __APP_VERSION__
const pwdOpen = ref(false)
const trashOpen = ref(false)
const sessions = ref([])
const sessionLoading = ref(false)
const exporting = ref('')
const tags = ref([])
const tagLoading = ref(false)
const photoStatus = ref({ enabled: false, available: false, message: '', provisionStatus: 'none' })
const photoRetrying = ref(false)

const photoTagText = computed(() => {
  if (photoStatus.value.available) return '已接入'
  if (photoStatus.value.provisionStatus === 'failed') return '开通失败'
  if (photoStatus.value.provisionStatus === 'pending') return '开通中'
  return '未接入'
})

const photoTagColor = computed(() => {
  if (photoStatus.value.available) return 'green'
  if (photoStatus.value.provisionStatus === 'failed') return 'red'
  if (photoStatus.value.provisionStatus === 'pending') return 'orange'
  return 'default'
})

const photoCanRetry = computed(
  () =>
    photoStatus.value.provisionStatus === 'failed' ||
    (photoStatus.value.enabled && !photoStatus.value.bound),
)

const photoDetail = computed(() => {
  if (photoStatus.value.available) {
    return '照片会保存到照片库，也可以从照片库导入已有照片。'
  }
  if (photoStatus.value.provisionStatus === 'failed') {
    return '照片库开通失败，照片仍会保存在服务器本机；可以点击“重试开通”。'
  }
  if (photoStatus.value.provisionStatus === 'pending') {
    return '正在为当前账号开通照片库，稍后刷新本页即可。'
  }
  return '照片库尚未接入，照片会保存在服务器本机；记录、上传、回收站均可正常使用。'
})

const user = computed(() => store.state.auth.userInfo || {})
const roleLabel = computed(() => (user.value.roleCode === 'OWNER' ? '所有者' : '成员'))
const trashKeepDays = computed(() => store.state.auth.settings?.trashKeepDays || 30)

const sessionColumns = [
  { title: '设备', key: 'device', width: 300, ellipsis: true },
  { title: 'IP', dataIndex: 'ip', key: 'ip', width: 130 },
  { title: '最近活跃', dataIndex: 'lastSeenAt', key: 'lastSeenAt', width: 170 },
  { title: '创建时间', dataIndex: 'createdAt', key: 'createdAt', width: 170 },
  { title: '操作', key: 'action', width: 90 },
]

const ICON_LABELS = {
  'lucide:footprints': '散步',
  'lucide:utensils': '美食',
  'lucide:plane': '旅行',
  'lucide:book-open': '阅读',
  'lucide:dumbbell': '运动',
  'lucide:users': '家人',
  'lucide:briefcase': '工作',
  'lucide:music': '音乐',
  'lucide:film': '电影',
  'lucide:cloud-sun': '天气',
  'lucide:coffee': '咖啡',
  'lucide:shopping-bag': '购物',
  'lucide:cat': '宠物',
  'lucide:pen-line': '记录',
  'lucide:leaf': '自然',
  'lucide:heart': '心情',
  'lucide:map-pin': '地点',
  'lucide:sun': '阳光',
  'lucide:star': '星星',
  'lucide:cloud': '云朵',
  'lucide:flower-2': '花草',
  'lucide:compass': '探索',
  'lucide:moon': '夜晚',
  'lucide:camera': '拍照',
  'lucide:clock': '时间',
  'lucide:sparkles': '灵感',
}

const iconOptions = TAG_ICON_OPTIONS.map((value) => ({
  value,
  label: ICON_LABELS[value] || value,
}))

function iconLabel(value) {
  return ICON_LABELS[value] || value
}

function tagOptions(tag) {
  const current = tag.icon || resolveTagIcon(tag.name)
  if (TAG_ICON_OPTIONS.includes(current)) return iconOptions
  return [{ value: current, label: iconLabel(current) }, ...iconOptions]
}

async function loadTags() {
  tagLoading.value = true
  try {
    tags.value = (await tagApi.list()) || []
  } finally {
    tagLoading.value = false
  }
}

async function saveTagIcon(tag, icon) {
  const saved = await tagApi.save({ id: tag.id, icon })
  tags.value = tags.value.map((item) => (item.id === tag.id ? saved : item))
  store.commit('app/bumpDataVersion', ['entries'])
  message.success('标签图标已更新')
}

async function loadPhotoStatus() {
  try {
    photoStatus.value = await immichApi.status()
  } catch {
    photoStatus.value = {
      enabled: false,
      available: false,
      message: '',
      provisionStatus: 'none',
    }
  }
}

async function retryPhoto() {
  photoRetrying.value = true
  try {
    await immichApi.credentialRetry()
    message.success('照片库已开通')
    await loadPhotoStatus()
  } finally {
    photoRetrying.value = false
  }
}

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

function onTrashChanged() {
  store.commit('app/bumpDataVersion', ['entries', 'stats'])
}

onMounted(() => {
  loadSessions()
  loadTags()
  loadPhotoStatus()
})
</script>

<style scoped lang="less">
.account-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-7);
}

.section-head {
  margin-bottom: 14px;
}

.export-hint {
  margin: 6px 0 0;
  font-size: 12px;
}

.trash-hint {
  margin: 0;
  font-size: 12px;
}

.tag-hint {
  font-size: 12px;
}

.tag-icon-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.tag-icon-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-1) 0;
}

.tag-icon-name {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--app-text-1);
}

.icon-option {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}

.info-text {
  margin: 0 0 var(--space-2);
  line-height: 1.8;
  font-size: 13px;
}

.photo-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
</style>
