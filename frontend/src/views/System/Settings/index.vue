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
            注册时必须填写有效邀请码。邀请码通过服务器命令
            <code>python -m app.cli create-invite --days 7</code> 生成。
          </p>
        </div>
      </a-spin>
    </section>

    <section class="surface">
      <div class="section-head">
        <strong>其他开关</strong>
      </div>
      <a-descriptions :column="1" bordered size="small">
        <a-descriptions-item label="AI 能力">
          {{ aiEnabled ? '已开启' : '未开启' }}
        </a-descriptions-item>
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
        接入后可在今天页从照片库导入已有照片。配置方式：在服务器的 .env 中设置
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
import { computed, onMounted, ref } from 'vue'

import { immichApi, systemApi } from '@/api/api'

const loading = ref(false)
const saving = ref(false)
const switches = ref({})
const registerMode = ref('CLOSED')
const photoStatus = ref({ enabled: false, available: false, message: '' })
const photoLoading = ref(false)

const aiEnabled = computed(() => switches.value.DAILYRECORD_AI_ENABLED === '1')
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
  } finally {
    loading.value = false
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
}

.mode-desc {
  margin-top: 12px;
  font-size: 13px;
  color: var(--app-text-2);

  p {
    margin: 0 0 6px;
  }

  code {
    padding: 1px 6px;
    border-radius: 6px;
    background: var(--app-bg-body);
    color: var(--app-primary);
  }
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
