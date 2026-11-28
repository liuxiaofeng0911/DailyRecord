<template>
  <div class="page settings-page">
    <div class="page-head">
      <h2 class="page-title">系统设置</h2>
      <p class="page-subtitle">控制注册开放程度与系统级开关，仅所有者可见。</p>
    </div>

    <section class="surface">
      <div class="row-between section-head">
        <strong>注册模式</strong>
        <a-button type="primary" :loading="saving" @click="saveRegisterMode">保存</a-button>
      </div>
      <a-spin :spinning="loading">
        <a-radio-group v-model:value="registerMode" :disabled="loading">
          <a-radio value="CLOSED">关闭注册</a-radio>
          <a-radio value="OPEN">开放注册</a-radio>
          <a-radio value="INVITE">邀请码注册</a-radio>
        </a-radio-group>
        <div class="mode-desc">
          <p v-if="registerMode === 'CLOSED'">
            注册页会提示联系所有者；你仍可在「用户管理」中直接创建账号。
          </p>
          <p v-else-if="registerMode === 'OPEN'">
            任何知道地址的人都可以注册，适合家庭内网或短期开放。建议用完及时关闭。
          </p>
          <p v-else>
            注册时必须填写有效邀请码，可在下方「邀请码」中生成后发给家人。
          </p>
        </div>
      </a-spin>
    </section>

    <section class="surface">
      <div class="row-between section-head">
        <strong>业务配置</strong>
        <div class="config-actions">
          <span class="muted">保存后立即生效，无需重启</span>
          <a-button type="primary" :loading="configSaving" @click="saveBusinessConfig">保存</a-button>
        </div>
      </div>
      <a-spin :spinning="loading">
        <a-form layout="vertical" class="config-form">
          <a-form-item
            label="单个文件上传上限（MB）"
            extra="照片与视频共用该上限；修改后今天页会同步显示最新限制。"
          >
            <a-input-number
              v-model:value="business.uploadMaxMb"
              :min="1"
              :max="2048"
              :precision="0"
              style="width: 200px"
            />
          </a-form-item>
          <a-form-item
            label="回收站保留天数"
            extra="删除的照片在回收站保留的天数，到期后由每日清理任务彻底删除。"
          >
            <a-input-number
              v-model:value="business.trashKeepDays"
              :min="1"
              :max="365"
              :precision="0"
              style="width: 200px"
            />
          </a-form-item>
          <a-form-item label="每日清理时间" extra="按东八区时间执行；修改后无需重启 api 服务。">
            <a-time-picker
              v-model:value="business.purgeTime"
              value-format="HH:mm"
              format="HH:mm"
              style="width: 200px"
            />
          </a-form-item>
          <a-form-item label="AI 自动注释">
            <a-switch
              v-model:checked="business.aiEnabled"
              checked-children="开启"
              un-checked-children="关闭"
            />
            <span class="muted config-inline">需确保 Ollama 已部署并加载视觉模型。</span>
          </a-form-item>
        </a-form>
      </a-spin>
    </section>

    <section class="surface">
      <div class="row-between section-head">
        <strong>邀请码</strong>
        <a-space>
          <a-input-number v-model:value="inviteDays" :min="1" :max="30" size="small" />
          <span class="muted">天后过期</span>
          <a-button type="primary" size="small" :loading="inviteCreating" @click="createInvite">
            生成邀请码
          </a-button>
        </a-space>
      </div>
      <a-alert v-if="newInvite.code" type="success" show-icon style="margin-bottom: 12px">
        <template #message>新邀请码（仅展示这一次，请立即复制）</template>
        <template #description>
          <div class="invite-code">
            <code>{{ newInvite.code }}</code>
            <a-button size="small" @click="copyInvite">复制</a-button>
          </div>
          <p class="muted">有效期至 {{ newInvite.expiresAt }}</p>
        </template>
      </a-alert>
      <a-table
        :columns="inviteColumns"
        :data-source="invites"
        row-key="id"
        size="small"
        :pagination="false"
        :loading="inviteLoading"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="inviteStatus(record).color">{{ inviteStatus(record).text }}</a-tag>
          </template>
        </template>
      </a-table>
      <p class="muted info-text invite-tip">
        邀请码只保存加密摘要，创建后无法再次查看，遗失请重新生成。
      </p>
    </section>

    <section class="surface">
      <div class="section-head">
        <strong>其他开关</strong>
      </div>
      <a-descriptions :column="1" bordered size="small">
        <a-descriptions-item label="初始化状态">
          {{ bootstrapDone ? '已完成' : '未完成' }}
        </a-descriptions-item>
      </a-descriptions>
    </section>

    <section class="surface">
      <div class="row-between section-head">
        <strong>照片库（Immich）</strong>
        <div class="photo-head">
          <a-tag :color="photoTagColor">{{ photoTagText }}</a-tag>
          <a-button size="small" :loading="photoLoading" @click="loadImmich">重新检测</a-button>
        </div>
      </div>
      <p class="muted info-text">{{ photoDetail }}</p>
      <p class="muted info-text">
        照片库是独立部署的服务。未接入时照片保存在服务器本机，记录、上传与回收站均可正常使用；
        接入后可在今天页把照片库里已有（例如手机自动备份）的照片直接加入记录。配置方式：在服务器的 .env 中设置
        IMMICH_URL 与 IMMICH_API_KEY，然后重启 api 服务。
      </p>
    </section>

    <section class="surface">
      <div class="section-head">
        <strong>关于邮箱</strong>
      </div>
      <p class="muted info-text">
        当前未接入邮件服务。邮箱只保存在服务器，不会对外发送，可用于登录或找回账号。
        后续配置邮件服务后，可支持自助找回密码；在此之前忘记密码请联系所有者重置。
      </p>
    </section>
  </div>
</template>

<script setup>
import { message } from 'antdv-next'
import { computed, onMounted, reactive, ref } from 'vue'
import { useStore } from 'vuex'

import { immichApi, systemApi } from '@/api/api'

const store = useStore()
const loading = ref(false)
const saving = ref(false)
const configSaving = ref(false)
const switches = ref({})
const registerMode = ref('CLOSED')
const business = reactive({
  uploadMaxMb: 200,
  trashKeepDays: 30,
  purgeTime: '03:30',
  aiEnabled: false,
})
const photoStatus = ref({ enabled: false, available: false, message: '' })
const photoLoading = ref(false)
const inviteDays = ref(7)
const invites = ref([])
const inviteLoading = ref(false)
const inviteCreating = ref(false)
const newInvite = reactive({ code: '', expiresAt: '' })

const inviteColumns = [
  { title: '生成时间', dataIndex: 'createdAt', key: 'createdAt', width: 180 },
  { title: '有效期至', dataIndex: 'expiresAt', key: 'expiresAt', width: 180 },
  { title: '状态', key: 'status', width: 100 },
]

const bootstrapDone = computed(() => switches.value.DAILYRECORD_BOOTSTRAP_DONE === 'Y')
const photoTagText = computed(() => {
  if (!photoStatus.value.enabled) return '未接入'
  return photoStatus.value.available ? '已接入' : '暂时不可用'
})
const photoTagColor = computed(() => {
  if (!photoStatus.value.enabled) return 'default'
  return photoStatus.value.available ? 'green' : 'orange'
})
const photoDetail = computed(() => {
  if (!photoStatus.value.enabled) {
    return '当前使用服务器本机存储，照片不会丢失。'
  }
  if (!photoStatus.value.available) {
    return photoStatus.value.message || '照片库暂时无法连接，照片会保存在服务器本机。'
  }
  return '照片库连接正常，上传照片会保存到照片库。'
})

async function load() {
  loading.value = true
  try {
    switches.value = (await systemApi.switchGet()) || {}
    registerMode.value = switches.value.DAILYRECORD_REGISTER_MODE || 'CLOSED'
    business.uploadMaxMb = Number(switches.value.DAILYRECORD_UPLOAD_MAX_MB) || 200
    business.trashKeepDays = Number(switches.value.DAILYRECORD_TRASH_KEEP_DAYS) || 30
    business.purgeTime = switches.value.DAILYRECORD_PURGE_TIME || '03:30'
    business.aiEnabled = switches.value.DAILYRECORD_AI_ENABLED === '1'
  } finally {
    loading.value = false
  }
}

async function saveBusinessConfig() {
  configSaving.value = true
  try {
    const payloads = [
      ['DAILYRECORD_UPLOAD_MAX_MB', String(business.uploadMaxMb || 200)],
      ['DAILYRECORD_TRASH_KEEP_DAYS', String(business.trashKeepDays || 30)],
      ['DAILYRECORD_PURGE_TIME', business.purgeTime || '03:30'],
      ['DAILYRECORD_AI_ENABLED', business.aiEnabled ? '1' : 'N'],
    ]
    const saved = {}
    for (const [key, enabled] of payloads) {
      Object.assign(saved, await systemApi.switchSave({ key, enabled }))
    }
    switches.value = { ...switches.value, ...saved }
    store.commit('auth/setSettings', {
      uploadMaxMb: Number(saved.DAILYRECORD_UPLOAD_MAX_MB) || business.uploadMaxMb,
      trashKeepDays: Number(saved.DAILYRECORD_TRASH_KEEP_DAYS) || business.trashKeepDays,
      aiEnabled: saved.DAILYRECORD_AI_ENABLED === '1',
    })
    message.success('业务配置已保存')
  } finally {
    configSaving.value = false
  }
}

async function saveRegisterMode() {
  saving.value = true
  try {
    const data = await systemApi.switchSave({
      key: 'DAILYRECORD_REGISTER_MODE',
      enabled: registerMode.value,
    })
    switches.value = { ...switches.value, ...data }
    message.success('注册设置已保存')
  } finally {
    saving.value = false
  }
}

function inviteStatus(record) {
  if (record.used) return { text: '已使用', color: 'default' }
  if (record.expired) return { text: '已过期', color: 'orange' }
  return { text: '可用', color: 'green' }
}

async function loadInvites() {
  inviteLoading.value = true
  try {
    invites.value = (await systemApi.inviteList()) || []
  } finally {
    inviteLoading.value = false
  }
}

async function createInvite() {
  inviteCreating.value = true
  try {
    const data = await systemApi.inviteCreate({ days: inviteDays.value || 7 })
    newInvite.code = data?.code || ''
    newInvite.expiresAt = data?.expiresAt || ''
    message.success('邀请码已生成')
    loadInvites()
  } finally {
    inviteCreating.value = false
  }
}

async function copyInvite() {
  try {
    await navigator.clipboard.writeText(newInvite.code)
    message.success('邀请码已复制')
  } catch {
    message.warning('复制失败，请手动选择邀请码复制')
  }
}

async function loadImmich() {
  photoLoading.value = true
  try {
    photoStatus.value = await immichApi.status()
  } catch {
    photoStatus.value = { enabled: false, available: false, message: '' }
  } finally {
    photoLoading.value = false
  }
}

onMounted(() => {
  load()
  loadInvites()
  loadImmich()
})
</script>

<style scoped lang="less">
.settings-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-7);
}

.section-head {
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.mode-desc {
  margin-top: 12px;
  font-size: 13px;
  color: var(--app-text-2);

  p {
    margin: 0 0 6px;
  }
}

.info-text {
  margin: 0 0 var(--space-2);
  line-height: 1.8;
  font-size: 13px;
}

.invite-code {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: 6px;

  code {
    padding: 2px 10px;
    border-radius: 6px;
    background: var(--app-bg-body);
    color: var(--app-primary);
    font-size: 14px;
    word-break: break-all;
  }
}

.invite-tip {
  margin: 12px 0 0;
}

.config-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.config-form {
  max-width: 620px;
}

.config-inline {
  margin-left: var(--space-3);
  font-size: 12px;
}

.photo-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

@media (max-width: 768px) {
  .config-actions {
    width: 100%;
    justify-content: space-between;
  }

  .config-form :deep(.ant-input-number),
  .config-form :deep(.ant-picker) {
    width: 100% !important;
  }

  .config-inline {
    display: block;
    margin: 6px 0 0;
  }
}
</style>
