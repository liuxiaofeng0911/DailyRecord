<template>
  <div class="auth-shell">
    <FloatingLines />
    <div class="auth-actions">
      <ThemeSelect />
    </div>
    <div class="auth-card">
      <div class="auth-card-inner">
        <div class="logo"><AppIcon name="lucide:calendar-heart" :size="24" /></div>
        <h1 class="auth-title">创建账号</h1>
        <p class="auth-subtitle">第一个注册的账号将成为系统所有者；之后的注册需要管理员开启注册。</p>

        <a-alert
          v-if="!registration.canRegister"
          type="warning"
          show-icon
          message="注册已关闭"
          description="请联系系统所有者在「系统管理 → 系统设置」中开启注册，或由所有者直接在用户管理中为你创建账号。"
          style="margin-bottom: 16px"
        />

        <a-form layout="vertical" @submit.prevent="submit">
          <a-form-item label="登录账号">
            <a-input v-model:value="form.userid" size="large" placeholder="3-32 位字母、数字或下划线" />
          </a-form-item>
          <a-form-item label="显示名">
            <a-input v-model:value="form.username" size="large" placeholder="在界面上如何称呼你" />
          </a-form-item>
          <a-form-item label="邮箱（仅保存在本机，作为唯一登录标识，不发送邮件）">
            <a-input v-model:value="form.email" size="large" placeholder="用于找回账号与登录" />
          </a-form-item>
          <a-form-item label="密码">
            <a-input-password v-model:value="form.password" size="large" placeholder="至少 10 位" />
          </a-form-item>
          <a-form-item label="确认密码">
            <a-input-password
              v-model:value="form.confirmPassword"
              size="large"
              placeholder="再次输入密码"
              @press-enter="submit"
            />
          </a-form-item>
          <a-form-item label="邀请码（需要时填写）">
            <a-input v-model:value="form.inviteCode" size="large" placeholder="可选" />
          </a-form-item>
          <a-button
            type="primary"
            size="large"
            block
            :loading="loading"
            :disabled="!registration.canRegister"
            @click="submit"
          >
            注册并登录
          </a-button>
        </a-form>

        <p class="footnote">
          已有账号？<router-link to="/Login">返回登录</router-link>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { message } from 'antdv-next'
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useStore } from 'vuex'

import { authApi } from '@/api/api'
import AppIcon from '@/components/AppIcon.vue'
import FloatingLines from '@/components/FloatingLines.vue'
import ThemeSelect from '@/components/ThemeSelect.vue'

const router = useRouter()
const store = useStore()
const loading = ref(false)
const registration = reactive({ loaded: false, canRegister: true, mode: 'CLOSED' })

onMounted(async () => {
  try {
    const info = await authApi.publicKey()
    registration.canRegister = info.canRegister !== false
    registration.mode = info.registerMode || 'CLOSED'
  } catch {
    // 公钥接口失败时交给提交阶段的错误提示
  } finally {
    registration.loaded = true
  }
})

const form = reactive({
  userid: '',
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
  inviteCode: '',
})

async function submit() {
  if (loading.value) return
  if (!form.userid.trim() || !form.username.trim() || !form.email.trim()) {
    message.warning('请完整填写账号、显示名和邮箱')
    return
  }
  if (form.password.length < 10) {
    message.warning('密码至少 10 位')
    return
  }
  if (form.password !== form.confirmPassword) {
    message.warning('两次输入的密码不一致')
    return
  }
  loading.value = true
  try {
    await store.dispatch('auth/register', {
      userid: form.userid.trim(),
      username: form.username.trim(),
      email: form.email.trim(),
      password: form.password,
      inviteCode: form.inviteCode.trim(),
    })
    await store.dispatch('dict/load')
    message.success('注册成功，开始记录吧')
    router.push('/Main/Today')
  } catch (error) {
    message.error(error?.message || '注册失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="less">
.logo {
  width: 46px;
  height: 46px;
  border-radius: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: linear-gradient(135deg, #2090ff, #7e57ff);
  margin-bottom: 14px;
}

.footnote {
  margin: 18px 0 0;
  font-size: 12px;
  color: var(--app-text-3);
  text-align: center;
}
</style>
