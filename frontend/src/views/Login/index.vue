<template>
  <div class="auth-shell">
    <FloatingLines />
    <div class="auth-actions">
      <ThemeSelect />
    </div>
    <div class="auth-card">
      <div class="auth-card-inner">
        <div class="logo"><AppIcon name="lucide:calendar-heart" :size="24" /></div>
        <h1 class="auth-title">每日记录</h1>
        <p class="auth-subtitle">每天一张照片，一句记忆点。登录后继续今天的记录。</p>

        <a-form layout="vertical" @submit.prevent="submit">
          <a-form-item label="账号或邮箱">
            <a-input
              v-model:value="form.identifier"
              size="large"
              placeholder="登录账号或邮箱"
              autocomplete="username"
              allow-clear
            />
          </a-form-item>
          <a-form-item label="密码">
            <a-input-password
              v-model:value="form.password"
              size="large"
              placeholder="请输入密码"
              autocomplete="current-password"
              @press-enter="submit"
            />
          </a-form-item>
          <div class="row-between remember-row">
            <a-checkbox v-model:checked="form.rememberMe">记住账号</a-checkbox>
            <router-link to="/Register">注册新账号</router-link>
          </div>
          <a-button type="primary" size="large" block :loading="loading" @click="submit">
            登录
          </a-button>
        </a-form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { message } from 'antdv-next'
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useStore } from 'vuex'

import AppIcon from '@/components/AppIcon.vue'
import FloatingLines from '@/components/FloatingLines.vue'
import ThemeSelect from '@/components/ThemeSelect.vue'

const router = useRouter()
const store = useStore()
const loading = ref(false)

const savedIdentifier = localStorage.getItem('dr:lastUser') || ''
const form = reactive({ identifier: savedIdentifier, password: '', rememberMe: true })

async function submit() {
  if (loading.value) return
  if (!form.identifier.trim() || !form.password) {
    message.warning('请填写账号和密码')
    return
  }
  loading.value = true
  try {
    await store.dispatch('auth/login', {
      identifier: form.identifier.trim(),
      password: form.password,
      rememberMe: form.rememberMe,
    })
    if (form.rememberMe) localStorage.setItem('dr:lastUser', form.identifier.trim())
    else localStorage.removeItem('dr:lastUser')
    await store.dispatch('dict/load')
    message.success('欢迎回来')
    router.push('/Main/Today')
  } catch (error) {
    message.error(error?.message || '登录失败，请检查账号和密码')
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

.remember-row {
  margin-bottom: 18px;
}
</style>
