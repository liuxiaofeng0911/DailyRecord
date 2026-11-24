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
          {{ aiEnabled ? '已开启（需同时配置 OLLAMA 环境变量）' : '未开启（P2，可后续接入本地模型）' }}
        </a-descriptions-item>
        <a-descriptions-item label="初始化状态">
          {{ bootstrapDone ? '已完成' : '未完成' }}
        </a-descriptions-item>
      </a-descriptions>
    </section>

    <section class="surface">
      <div class="section-head">
        <strong>关于邮箱</strong>
      </div>
      <p class="muted info-text">
        当前未接入邮件服务。邮箱只保存在本机数据库，作为账号的唯一标识与登录方式之一（也可用登录账号登录）。
        后续若配置 SMTP，可用于自助找回密码；在此之前忘记密码请联系所有者重置。
      </p>
    </section>
  </div>
</template>

<script setup>
import { message } from 'antdv-next'
import { computed, onMounted, ref } from 'vue'

import { systemApi } from '@/api/api'

const loading = ref(false)
const saving = ref(false)
const switches = ref({})
const registerMode = ref('CLOSED')

const aiEnabled = computed(() => switches.value.DAILYRECORD_AI_ENABLED === '1')
const bootstrapDone = computed(() => switches.value.DAILYRECORD_BOOTSTRAP_DONE === 'Y')

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

onMounted(load)
</script>

<style scoped lang="less">
.settings-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
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
  margin: 0;
  line-height: 1.8;
  font-size: 13px;
}
</style>
